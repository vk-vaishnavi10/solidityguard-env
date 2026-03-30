"""
Smart contract corpus for SolidityGuard-Env.
Each task contains:
  - A vulnerable Solidity contract (source code string)
  - Ground truth vulnerabilities
  - Accepted patches per vuln
  - ABI summary
"""

# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — EASY: Classic Reentrancy (inspired by The DAO hack 2016)
# ─────────────────────────────────────────────────────────────────────────────

TASK1_CONTRACT = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleBank {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");

        // VULNERABILITY: external call before state update
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        balances[msg.sender] -= amount;  // state updated AFTER call
    }

    function getBalance() external view returns (uint256) {
        return balances[msg.sender];
    }
}
"""

TASK1_ABI = [
    {"function": "deposit", "visibility": "external", "mutability": "payable"},
    {"function": "withdraw", "inputs": ["uint256 amount"], "visibility": "external"},
    {"function": "getBalance", "visibility": "external", "mutability": "view"},
]

TASK1_GROUND_TRUTH = {
    "vulnerabilities": [
        {
            "vuln_id": "REENTRANCY-001",
            "name": "Reentrancy",
            "severity": "critical",
            "location": "withdraw",
            "description": "External call is made before state update, allowing recursive reentry.",
            "keywords": ["reentrancy", "reentrant", "reentrancy attack", "recursive", "dao", "call before state"],
        }
    ],
    "accepted_patches": {
        "REENTRANCY-001": [
            "checks-effects-interactions",
            "update state before external call",
            "balances[msg.sender] -= amount before call",
            "reentrancyguard",
            "nonreentrant modifier",
            "mutex",
        ]
    }
}

TASK1_DESCRIPTION = (
    "Audit the SimpleBank smart contract. "
    "Find all security vulnerabilities, report each one with its severity and the vulnerable function name. "
    "This contract handles real ETH — a bug could drain all funds."
)

# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — MEDIUM: Reentrancy + Missing Access Control + tx.origin auth
# ─────────────────────────────────────────────────────────────────────────────

TASK2_CONTRACT = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract VaultManager {
    address public owner;
    mapping(address => uint256) public balances;
    bool public paused;

    constructor() {
        owner = msg.sender;
    }

    // VULNERABILITY 1: tx.origin used for authentication (phishing risk)
    modifier onlyOwner() {
        require(tx.origin == owner, "Not owner");
        _;
    }

    function pause() external onlyOwner {
        paused = true;
    }

    function unpause() external onlyOwner {
        paused = false;
    }

    function deposit() external payable {
        require(!paused, "Paused");
        balances[msg.sender] += msg.value;
    }

    // VULNERABILITY 2: Reentrancy — state updated after call
    function withdraw(uint256 amount) external {
        require(!paused, "Paused");
        require(balances[msg.sender] >= amount, "Insufficient");

        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "Transfer failed");
        balances[msg.sender] -= amount;
    }

    // VULNERABILITY 3: Anyone can call emergencyDrain, no access control
    function emergencyDrain() external {
        payable(msg.sender).transfer(address(this).balance);
    }

    receive() external payable {}
}
"""

TASK2_ABI = [
    {"function": "pause", "visibility": "external", "modifier": "onlyOwner"},
    {"function": "unpause", "visibility": "external", "modifier": "onlyOwner"},
    {"function": "deposit", "visibility": "external", "mutability": "payable"},
    {"function": "withdraw", "inputs": ["uint256 amount"], "visibility": "external"},
    {"function": "emergencyDrain", "visibility": "external"},
]

TASK2_GROUND_TRUTH = {
    "vulnerabilities": [
        {
            "vuln_id": "TXORIGIN-001",
            "name": "tx.origin Authentication",
            "severity": "high",
            "location": "onlyOwner",
            "description": "tx.origin used for auth — vulnerable to phishing via malicious intermediary contracts.",
            "keywords": ["tx.origin", "txorigin", "phishing", "origin", "msg.sender instead"],
        },
        {
            "vuln_id": "REENTRANCY-001",
            "name": "Reentrancy",
            "severity": "critical",
            "location": "withdraw",
            "description": "State updated after external call in withdraw().",
            "keywords": ["reentrancy", "reentrant", "call before state", "withdraw", "recursive"],
        },
        {
            "vuln_id": "ACCESS-001",
            "name": "Missing Access Control",
            "severity": "critical",
            "location": "emergencyDrain",
            "description": "emergencyDrain() has no access control — anyone can drain the vault.",
            "keywords": ["access control", "authorization", "onlyowner", "emergency", "drain", "anyone"],
        },
    ],
    "accepted_patches": {
        "TXORIGIN-001": ["use msg.sender", "replace tx.origin with msg.sender", "msg.sender == owner"],
        "REENTRANCY-001": ["checks-effects-interactions", "update state before call", "nonreentrant", "reentrancyguard", "mutex"],
        "ACCESS-001": ["add onlyOwner modifier", "require msg.sender == owner", "access control", "restrict emergencyDrain"],
    }
}

TASK2_DESCRIPTION = (
    "Audit the VaultManager contract. It manages ETH deposits for multiple users and has an emergency drain function. "
    "Find ALL vulnerabilities — there are multiple. Report each with severity (critical/high/medium/low) "
    "and the exact function or modifier where it occurs."
)

# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — HARD: DeFi lending pool — 4 vulns + must patch all
# ─────────────────────────────────────────────────────────────────────────────

TASK3_CONTRACT = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract LendingPool {
    IERC20 public token;
    address public admin;

    mapping(address => uint256) public deposits;
    mapping(address => uint256) public borrows;
    mapping(address => uint256) public lastInterestBlock;

    uint256 public constant INTEREST_RATE = 5;   // 5% per 100 blocks
    uint256 public constant COLLATERAL_RATIO = 150; // 150%

    constructor(address _token) {
        token = IERC20(_token);
        admin = msg.sender;
    }

    // VULNERABILITY 1: No reentrancy guard on flashLoan
    function flashLoan(uint256 amount, address target, bytes calldata data) external {
        uint256 balBefore = token.balanceOf(address(this));
        token.transfer(target, amount);

        // arbitrary external call — allows reentrant deposit/borrow manipulation
        (bool ok, ) = target.call(data);
        require(ok, "Callback failed");

        uint256 balAfter = token.balanceOf(address(this));
        require(balAfter >= balBefore, "Flash loan not repaid");
    }

    // VULNERABILITY 2: Integer precision loss — division before multiplication
    function calculateInterest(address user) public view returns (uint256) {
        uint256 blocksDelta = block.number - lastInterestBlock[user];
        // precision loss: integer division truncates before multiplication
        return borrows[user] * (blocksDelta / 100) * INTEREST_RATE / 100;
    }

    function deposit(uint256 amount) external {
        token.transferFrom(msg.sender, address(this), amount);
        deposits[msg.sender] += amount;
        lastInterestBlock[msg.sender] = block.number;
    }

    // VULNERABILITY 3: Oracle manipulation — uses spot balance as price oracle
    function borrow(uint256 amount) external {
        uint256 poolBalance = token.balanceOf(address(this));  // manipulable via flashloan
        uint256 userDeposit = deposits[msg.sender];
        uint256 maxBorrow = (userDeposit * 100) / COLLATERAL_RATIO;

        // uses pool balance as a naive price signal — flash loan can inflate this
        require(amount <= maxBorrow && amount <= poolBalance, "Over collateral limit");
        borrows[msg.sender] += amount;
        token.transfer(msg.sender, amount);
    }

    // VULNERABILITY 4: Admin can rug — no timelock on token swap
    function setToken(address newToken) external {
        require(msg.sender == admin, "Not admin");
        // no timelock — admin can instantly swap token to worthless contract
        token = IERC20(newToken);
    }

    function repay(uint256 amount) external {
        uint256 interest = calculateInterest(msg.sender);
        uint256 total = borrows[msg.sender] + interest;
        require(amount <= total, "Overpayment");
        token.transferFrom(msg.sender, address(this), amount);
        borrows[msg.sender] = total - amount;
        lastInterestBlock[msg.sender] = block.number;
    }
}
"""

TASK3_ABI = [
    {"function": "flashLoan", "inputs": ["uint256 amount", "address target", "bytes data"], "visibility": "external"},
    {"function": "calculateInterest", "inputs": ["address user"], "visibility": "public", "mutability": "view"},
    {"function": "deposit", "inputs": ["uint256 amount"], "visibility": "external"},
    {"function": "borrow", "inputs": ["uint256 amount"], "visibility": "external"},
    {"function": "setToken", "inputs": ["address newToken"], "visibility": "external"},
    {"function": "repay", "inputs": ["uint256 amount"], "visibility": "external"},
]

TASK3_GROUND_TRUTH = {
    "vulnerabilities": [
        {
            "vuln_id": "REENTRANCY-001",
            "name": "Flash Loan Reentrancy",
            "severity": "critical",
            "location": "flashLoan",
            "description": "flashLoan makes arbitrary external call with no reentrancy protection, enabling reentrant deposits/borrows.",
            "keywords": ["reentrancy", "flashloan", "flash loan", "callback", "reentrant", "nonreentrant"],
        },
        {
            "vuln_id": "PRECISION-001",
            "name": "Integer Precision Loss",
            "severity": "medium",
            "location": "calculateInterest",
            "description": "Division before multiplication causes precision loss — users pay less interest than intended.",
            "keywords": ["precision", "integer division", "division before multiplication", "truncation", "rounding"],
        },
        {
            "vuln_id": "ORACLE-001",
            "name": "Price Oracle Manipulation",
            "severity": "critical",
            "location": "borrow",
            "description": "Uses spot token balance as price oracle — manipulable via flash loan to bypass collateral checks.",
            "keywords": ["oracle", "price manipulation", "flash loan", "spot price", "balanceof", "manipulation"],
        },
        {
            "vuln_id": "RUGPULL-001",
            "name": "Admin Rug Pull (No Timelock)",
            "severity": "high",
            "location": "setToken",
            "description": "Admin can instantly replace token contract with no timelock, effectively rugging all depositors.",
            "keywords": ["timelock", "rug", "rugpull", "rug pull", "admin", "no delay", "settoken", "centralization"],
        },
    ],
    "accepted_patches": {
        "REENTRANCY-001": ["nonreentrant modifier", "reentrancyguard", "checks-effects-interactions", "state lock before call"],
        "PRECISION-001": ["multiply before divide", "borrows[user] * blocksDelta * INTEREST_RATE / 10000", "fixed point math", "precision fix"],
        "ORACLE-001": ["use chainlink oracle", "twap", "time-weighted average price", "external price feed", "avoid spot balance"],
        "RUGPULL-001": ["timelock", "add delay", "governance", "timelockcontroller", "2 day delay", "multisig"],
    }
}

TASK3_DESCRIPTION = (
    "Audit this DeFi LendingPool contract that handles ERC-20 token deposits, borrowing, and flash loans. "
    "This is a production-grade contract managing potentially millions in user funds. "
    "Find ALL vulnerabilities (there are 4), report each with severity and location, "
    "then suggest a concrete patch for each one. Miss any and real users get rekt."
)

# ─────────────────────────────────────────────────────────────────────────────
# TASK 4 — MEDIUM: NFT Minting — Front-Running + Unrestricted Mint
# ─────────────────────────────────────────────────────────────────────────────

TASK4_CONTRACT = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IERC721 {
    function transferFrom(address from, address to, uint256 tokenId) external;
}

contract NFTMint {
    address public owner;
    uint256 public totalSupply;
    uint256 public maxSupply = 1000;
    uint256 public mintPrice = 0.05 ether;

    mapping(uint256 => address) public tokenOwner;
    mapping(address => uint256) public mintedCount;

    // VULNERABILITY 1: Predictable randomness — block.timestamp used for "random" tokenId
    // Miners can manipulate block.timestamp to get rare NFTs
    function mint() external payable {
        require(msg.value >= mintPrice, "Insufficient payment");
        require(totalSupply < maxSupply, "Sold out");

        // "random" tokenId based on predictable on-chain data — manipulable
        uint256 tokenId = uint256(
            keccak256(abi.encodePacked(block.timestamp, msg.sender, totalSupply))
        ) % maxSupply;

        tokenOwner[tokenId] = msg.sender;
        mintedCount[msg.sender]++;
        totalSupply++;
    }

    // VULNERABILITY 2: Front-running — whitelist check uses public mempool data
    // Attacker sees pending tx and front-runs with higher gas to steal the mint
    mapping(address => bool) public whitelist;

    function whitelistMint(address user) external payable {
        require(whitelist[user], "Not whitelisted");
        require(msg.value >= mintPrice, "Insufficient payment");
        require(totalSupply < maxSupply, "Sold out");

        uint256 tokenId = totalSupply;
        tokenOwner[tokenId] = msg.sender;  // uses msg.sender not user — anyone can call
        mintedCount[msg.sender]++;
        totalSupply++;
    }

    // VULNERABILITY 3: No withdrawal function — ETH trapped in contract forever
    constructor() {
        owner = msg.sender;
    }

    function addToWhitelist(address user) external {
        require(msg.sender == owner, "Not owner");
        whitelist[user] = true;
    }

    // Missing: withdraw() function — all mint revenue permanently locked
}
"""

TASK4_ABI = [
    {"function": "mint", "visibility": "external", "mutability": "payable"},
    {"function": "whitelistMint", "inputs": ["address user"], "visibility": "external", "mutability": "payable"},
    {"function": "addToWhitelist", "inputs": ["address user"], "visibility": "external"},
]

TASK4_GROUND_TRUTH = {
    "vulnerabilities": [
        {
            "vuln_id": "RANDOMNESS-001",
            "name": "Weak Randomness",
            "severity": "high",
            "location": "mint",
            "description": "block.timestamp used as randomness source — miners can manipulate to predict or influence tokenId assignment.",
            "keywords": ["randomness", "block.timestamp", "timestamp", "predictable", "manipulate", "miner", "weak random"],
        },
        {
            "vuln_id": "FRONTRUN-001",
            "name": "Front-Running",
            "severity": "high",
            "location": "whitelistMint",
            "description": "whitelistMint uses msg.sender instead of the user param — anyone watching mempool can front-run and steal whitelist mint.",
            "keywords": ["front-running", "frontrun", "mempool", "msg.sender", "sandwich", "front run"],
        },
        {
            "vuln_id": "LOCKED-ETH-001",
            "name": "Locked Ether",
            "severity": "medium",
            "location": "contract",
            "description": "Contract accepts ETH via mint() but has no withdraw() function — all revenue permanently locked.",
            "keywords": ["locked ether", "locked eth", "no withdraw", "withdraw", "stuck", "trapped", "funds locked"],
        },
    ],
    "accepted_patches": {
        "RANDOMNESS-001": ["chainlink vrf", "use vrf", "verifiable random", "commit-reveal", "off-chain randomness"],
        "FRONTRUN-001": ["use user parameter", "replace msg.sender with user", "commit-reveal scheme", "fix msg.sender"],
        "LOCKED-ETH-001": ["add withdraw function", "withdrawal pattern", "payable owner withdraw", "call{value: address(this).balance}"],
    }
}

TASK4_DESCRIPTION = (
    "Audit this NFT minting contract used by a 1000-supply collection. "
    "Find all vulnerabilities: weak randomness that lets miners snipe rare NFTs, "
    "a front-running flaw in the whitelist mint, and any ETH handling issues. "
    "There are 3 vulnerabilities — report each with severity and the affected function."
)

# ─────────────────────────────────────────────────────────────────────────────
# TASK 5 — HARD: ERC-20 Token — Approval Exploit + Permit Replay + Overflow
# ─────────────────────────────────────────────────────────────────────────────

TASK5_CONTRACT = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract VulnToken {
    string public name = "VulnToken";
    string public symbol = "VULN";
    uint8 public decimals = 18;
    uint256 public totalSupply;

    address public owner;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    // EIP-2612 permit
    mapping(address => uint256) public nonces;
    bytes32 public DOMAIN_SEPARATOR;

    constructor(uint256 _supply) {
        owner = msg.sender;
        totalSupply = _supply;
        balanceOf[msg.sender] = _supply;
        DOMAIN_SEPARATOR = keccak256(abi.encode(
            keccak256("EIP712Domain(string name,uint256 chainId,address verifyingContract)"),
            keccak256(bytes(name)),
            block.chainid,
            address(this)
        ));
    }

    // VULNERABILITY 1: Approval race condition
    // Standard ERC-20 approve() allows a spender to spend both old and new allowance
    // if they front-run the approval change
    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(balanceOf[from] >= amount, "Insufficient balance");
        require(allowance[from][msg.sender] >= amount, "Insufficient allowance");
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    // VULNERABILITY 2: Permit signature replay across chains
    // DOMAIN_SEPARATOR includes chainId at construction but not at call time
    // After a chain fork, old signatures are valid on both chains
    bytes32 public constant PERMIT_TYPEHASH = keccak256(
        "Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)"
    );

    function permit(
        address _owner, address spender, uint256 value,
        uint256 deadline, uint8 v, bytes32 r, bytes32 s
    ) external {
        require(deadline >= block.timestamp, "Expired");
        bytes32 digest = keccak256(abi.encodePacked(
            "\\x19\\x01",
            DOMAIN_SEPARATOR,  // cached at deploy — not recomputed with current chainId
            keccak256(abi.encode(PERMIT_TYPEHASH, _owner, spender, value, nonces[_owner]++, deadline))
        ));
        address recovered = ecrecover(digest, v, r, s);
        require(recovered == _owner, "Invalid signature");
        allowance[_owner][spender] = value;
    }

    // VULNERABILITY 3: Unrestricted mint — no access control
    function mint(address to, uint256 amount) external {
        // Missing: require(msg.sender == owner) — anyone can mint infinite tokens
        balanceOf[to] += amount;
        totalSupply += amount;
    }

    // VULNERABILITY 4: Fee-on-transfer inconsistency
    // transferFrom doesn't account for fee, causing accounting errors in DeFi integrations
    uint256 public feePercent = 1;  // 1% fee

    function transferWithFee(address to, uint256 amount) external returns (bool) {
        uint256 fee = amount * feePercent / 100;
        uint256 netAmount = amount - fee;
        require(balanceOf[msg.sender] >= amount, "Insufficient");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += netAmount;   // recipient gets less than amount
        balanceOf[owner] += fee;
        // But transferFrom doesn't apply fee — inconsistency exploitable
        return true;
    }
}
"""

TASK5_ABI = [
    {"function": "approve", "inputs": ["address spender", "uint256 amount"], "visibility": "external"},
    {"function": "transferFrom", "inputs": ["address from", "address to", "uint256 amount"], "visibility": "external"},
    {"function": "transfer", "inputs": ["address to", "uint256 amount"], "visibility": "external"},
    {"function": "permit", "inputs": ["address owner", "address spender", "uint256 value", "uint256 deadline", "uint8 v", "bytes32 r", "bytes32 s"], "visibility": "external"},
    {"function": "mint", "inputs": ["address to", "uint256 amount"], "visibility": "external"},
    {"function": "transferWithFee", "inputs": ["address to", "uint256 amount"], "visibility": "external"},
]

TASK5_GROUND_TRUTH = {
    "vulnerabilities": [
        {
            "vuln_id": "APPROVAL-001",
            "name": "ERC-20 Approval Race Condition",
            "severity": "high",
            "location": "approve",
            "description": "Standard approve() is vulnerable to front-running — spender can spend both old and new allowance if they front-run the change.",
            "keywords": ["approval", "race condition", "front-run", "allowance", "approve", "increaseAllowance", "erc20 approval"],
        },
        {
            "vuln_id": "REPLAY-001",
            "name": "Permit Signature Replay (Cross-Chain)",
            "severity": "high",
            "location": "permit",
            "description": "DOMAIN_SEPARATOR cached at deployment — after a chain fork, permit signatures are replayable on both chains.",
            "keywords": ["replay", "signature replay", "cross-chain", "domain separator", "chain fork", "chainid", "permit"],
        },
        {
            "vuln_id": "UNAUTH-MINT-001",
            "name": "Unrestricted Mint",
            "severity": "critical",
            "location": "mint",
            "description": "mint() has no access control — any address can mint unlimited tokens, inflating supply and destroying token value.",
            "keywords": ["unrestricted mint", "access control", "mint", "anyone can mint", "no authorization", "missing require"],
        },
        {
            "vuln_id": "FEE-INCONSISTENCY-001",
            "name": "Fee-on-Transfer Inconsistency",
            "severity": "medium",
            "location": "transferWithFee",
            "description": "transferWithFee applies fee but transferFrom does not — DeFi protocols integrating this token will have accounting errors.",
            "keywords": ["fee", "fee on transfer", "inconsistency", "accounting", "deflationary", "transfer fee"],
        },
    ],
    "accepted_patches": {
        "APPROVAL-001": ["use increaseAllowance", "increaseAllowance decreaseAllowance", "safeapprove", "require current allowance is 0"],
        "REPLAY-001": ["recompute domain separator", "use block.chainid at call time", "dynamic domain separator", "check chainid in permit"],
        "UNAUTH-MINT-001": ["add require msg.sender == owner", "access control", "onlyOwner modifier", "restrict mint"],
        "FEE-INCONSISTENCY-001": ["apply fee in transferFrom", "consistent fee logic", "remove fee or apply everywhere"],
    }
}

TASK5_DESCRIPTION = (
    "Audit this ERC-20 token contract implementing standard transfers and EIP-2612 permit. "
    "This token is about to list on a major DEX — any vulnerability could be exploited at launch. "
    "Find all 4 vulnerabilities including the approval race condition, permit replay attack, "
    "access control flaw, and fee inconsistency. Report each with severity and suggest patches."
)

# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

TASKS = {
    "task1": {
        "contract_name": "SimpleBank",
        "source_code": TASK1_CONTRACT,
        "abi_summary": TASK1_ABI,
        "ground_truth": TASK1_GROUND_TRUTH,
        "description": TASK1_DESCRIPTION,
        "difficulty": "easy",
        "total_vulns": 1,
    },
    "task2": {
        "contract_name": "VaultManager",
        "source_code": TASK2_CONTRACT,
        "abi_summary": TASK2_ABI,
        "ground_truth": TASK2_GROUND_TRUTH,
        "description": TASK2_DESCRIPTION,
        "difficulty": "medium",
        "total_vulns": 3,
    },
    "task3": {
        "contract_name": "LendingPool",
        "source_code": TASK3_CONTRACT,
        "abi_summary": TASK3_ABI,
        "ground_truth": TASK3_GROUND_TRUTH,
        "description": TASK3_DESCRIPTION,
        "difficulty": "hard",
        "total_vulns": 4,
    },
    "task4": {
        "contract_name": "NFTMint",
        "source_code": TASK4_CONTRACT,
        "abi_summary": TASK4_ABI,
        "ground_truth": TASK4_GROUND_TRUTH,
        "description": TASK4_DESCRIPTION,
        "difficulty": "medium",
        "total_vulns": 3,
    },
    "task5": {
        "contract_name": "VulnToken",
        "source_code": TASK5_CONTRACT,
        "abi_summary": TASK5_ABI,
        "ground_truth": TASK5_GROUND_TRUTH,
        "description": TASK5_DESCRIPTION,
        "difficulty": "hard",
        "total_vulns": 4,
    },
}