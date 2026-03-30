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
}