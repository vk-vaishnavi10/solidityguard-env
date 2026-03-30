# ⚡ ZeroShield
### *AI-Powered Parametric Income Insurance for Q-Commerce Delivery Partners*

> **Guidewire DEVTrails 2026** · Phase 1 — Ideation & Foundation  
> Persona: **Q-Commerce Riders** (Zepto / Blinkit / Swiggy Instamart)

---

## 🎯 The Problem We're Solving

India's Q-Commerce riders (Zepto, Blinkit, Swiggy Instamart) are locked to a **fixed dark store zone** of 2–5 km. They must complete deliveries in under 10 minutes and earn purely per-order. When an external disruption hits their zone — heavy rain, a heatwave, a spike in pollution, a curfew — their income drops to **zero instantly**.

Unlike food delivery riders who can reroute, Q-commerce riders **cannot leave their zone**. One flooded street = one lost shift. One lost shift = no safety net.

> **No insurance product today covers hyperlocal, zone-level income loss. ZeroShield is the first.**

---

## 👤 Persona & Scenarios

### Primary Persona: Ravi, 26 — Zepto Rider, Kondapur Dark Store, Hyderabad

- Works 6 days/week, 8–10 hours/day
- Earns ₹600–₹900/day (≈ ₹4,200–₹6,300/week)
- Has no savings buffer — misses rent if he loses 2 days of income
- Pays ₹50/week for ZeroShield Standard coverage

**Scenario 1 — Heavy Rain**
> 6 PM Thursday. Flash flooding hits Kondapur main road. Orders drop 90% in Ravi's zone. ZeroShield's rain trigger fires (>15mm/hr via Weather API). Claim auto-initiated. Fraud check passes. ₹900 payout credited to Ravi's UPI in under 4 minutes. He filed nothing.

**Scenario 2 — Heatwave**
> 2 PM, peak summer. Heat index crosses 43°C in Ravi's zone. Open-Meteo API records the breach. Order volume drops >60% vs Ravi's 4-week baseline for that time slot. ZeroShield auto-triggers a partial payout of ₹320 for the 2-hour window.

**Scenario 3 — High Pollution**
> AQI spikes to 320 (Hazardous) in Ravi's zone during smog season. WAQI API fires the pollution trigger. GPS confirms Ravi is active in the zone. Payout: ₹280 for the affected shift window.

**Scenario 4 — Zone Curfew / Lockdown**
> Sudden Section 144 imposed in Ravi's delivery zone. Mock civic alert feed triggers ZeroShield's social disruption parameter. Full shift payout activated: ₹900.

---

## 🏗️ Platform Architecture

Our platform follows a clean **6-layer pipeline** as shown below:

```
┌─────────────┐    ┌─────────────┐    ┌──────────────────────────────────────┐
│  Worker App │───▶│ API Gateway │───▶│           Core Services              │
│  (Frontend) │    │  (Backend)  │    │  1. User Management                  │
│             │    │             │    │  2. Policy Engine                    │
│ • Weekly    │    │ • Auth      │    │  3. Claims Processor                 │
│   Coverage  │    │ • Routing   │    │  4. Payment Service (Razorpay)       │
│ • Risk      │    │ • Rate      │    ├──────────────────────────────────────┤
│   Alerts    │    │   Limiting  │    │           AI/ML Engine               │
│ • Payout    │    │ • Caching   │    │  • Risk Prediction AI                │
│   History   │    │             │    │  • Dynamic Pricing AI                │
│ • Earnings  │    │             │    │  • Fraud Detection AI                │
│   Dashboard │    │             │    ├──────────────────────────────────────┤
└─────────────┘    └─────────────┘    │           Data Sources               │
                                      │  • Weather API  • Pollution API      │
                                      │  • Traffic API                       │
                                      └──────────────┬───────────────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────────────┐
                                      │      Parametric Trigger Engine       │
                                      │   Heavy Rain | Heatwave | High AQI   │
                                      │   Zone Lockdown | Platform Outage    │
                                      └──────────────┬───────────────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────────────┐
                                      │     Fraud Protection & Security      │
                                      │    GPS Check | Claims AI | Risk      │
                                      │         Analytics Engine             │
                                      └──────────────┬───────────────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────────────┐
                                      │           Payout System              │
                                      │     Instant Payout via UPI /         │
                                      │         Bank Transfer                │
                                      └──────────────────────────────────────┘
```

---

## 📱 Layer 1 — Worker App (Frontend)

The rider-facing Progressive Web App (PWA), accessible on both mobile and web.

**Key screens:**
- **Weekly Coverage** — active plan, premium paid (e.g. ₹50 Premium)
- **Risk Alerts** — live disruption notifications for the rider's zone
- **Payout History** — all past claims and credited amounts
- **Earnings Dashboard** — weekly income trends and protected hours

**Tech:** React Native Web / Expo (single codebase for Android, iOS, Web)  
**Auth:** Firebase OTP login — phone number only, zero friction for riders

---

## 🔌 Layer 2 — API Gateway (Backend)

Single entry point for all client and admin requests.

- Authentication and session validation (Firebase Auth)
- Rate limiting and abuse protection
- Request routing to the appropriate core service
- Response caching via Redis for weather and AQI data
- Webhook listener for Razorpay payout callbacks

**Tech:** FastAPI (Python) · Redis (Upstash free tier) · Firebase Auth

---

## ⚙️ Layer 3 — Core Services

### 3.1 User Management
- Rider registration with Aadhaar / phone verification
- Dark store zone selection and GPS pin registration on map
- Weekly earnings declaration (used for payout calculation)
- Plan subscription management (Basic / Standard / Premium)

### 3.2 Policy Engine
- Creates weekly policy on Monday 00:00, expires Sunday 23:59
- Calls ShiftGuard Dynamic Pricing AI to compute personalized premium
- Sends renewal nudge every Sunday with next-week risk forecast
- Manages policy state: Active → Disrupted → Claim Initiated → Settled

### 3.3 Claims Processor
- Receives trigger event from Parametric Trigger Engine
- Calls Fraud Detection AI to score the claim
- Auto-approves claims with fraud score < 0.75
- Flags high-score claims for manual admin review (notified within 15 min)
- Passes approved claims to Payment Service

### 3.4 Payment Service (Razorpay)
- Razorpay Test Mode for payout simulation in Phase 1–2
- Live Razorpay in Phase 3
- Supports UPI (instant) and Bank Transfer (fallback)
- Target: payout credited within **5 minutes** of trigger fire
- Full transaction ledger with audit trail

---

## 🤖 Layer 3b — AI/ML Engine

### Risk Prediction AI
| | |
|---|---|
| **Model** | Gradient Boosted Regressor (XGBoost) |
| **Inputs** | Zone flood history, AQI frequency, rider tenure, zone claim density, season |
| **Output** | Weekly risk score per zone (0–100) |
| **Used by** | Policy Engine for zone risk multiplier |
| **Retrain** | Every Sunday midnight |

### Dynamic Pricing AI
**Premium Formula:**
```
Final Weekly Premium = Base Tier × Zone Risk Multiplier × Season Factor × Claim History Modifier

Zone Risk Multiplier   → 0.85 (low-risk zone)  to  1.40 (flood-prone zone)
Season Factor          → 1.00 (normal) | 1.15 (peak summer) | 1.25 (monsoon)
Claim History Modifier → 0.95 (no claims) | 1.10 (1 claim) | 1.30 (2+ claims)
```

**Live example — Ravi, Standard Plan, Monsoon, Kondapur zone:**
```
₹39  ×  1.20 (zone risk)  ×  1.25 (monsoon)  ×  1.00 (no claims)  =  ₹58.5  →  ₹59/week
```

### Fraud Detection AI
| | |
|---|---|
| **Model** | Isolation Forest (unsupervised anomaly detection) |
| **Inputs** | GPS zone consistency score, collective order drop %, deviation from earning baseline, claim frequency |
| **Output** | Fraud probability score (0–1). Score > 0.75 → flagged |
| **Key rule** | If orders were flowing in the zone during claimed disruption → suspicious |
| **Phase 1** | Bootstrapped with synthetic data |
| **Phase 2+** | Retrained on real claims |

---

## 🌐 Layer 3c — Data Sources

| Source | API | What We Pull | Trigger It Powers |
|--------|-----|-------------|-------------------|
| **Weather API** | OpenWeatherMap (free tier) | Rainfall mm/hr, wind speed | Heavy Rain (>15mm/hr) |
| **Pollution API** | WAQI API (free tier) | AQI index per pin location | High Pollution (AQI >300) |
| **Traffic API** | Mock / TomTom sandbox | Road closure flags, zone access status | Zone Blockage |

All sources polled every **5 minutes** via background cron job running on the API server.

---

## ⚡ Layer 4 — Parametric Trigger Engine

The core engine. Monitors all data feeds and fires claims automatically — no rider action required.

| # | Trigger | Fire Condition | Type |
|---|---------|----------------|------|
| 1 | 🌧️ Heavy Rain | Rainfall > 15mm/hr in rider's 3km zone | Environmental |
| 2 | ☀️ Heatwave | Feels-like temp > 42°C during active shift | Environmental |
| 3 | 💨 High Pollution | AQI > 300 (Hazardous) in rider's zone | Environmental |
| 4 | 🚧 Zone Curfew / Lockdown | Government alert tag in active delivery zone | Social |
| 5 | ⚡ Platform Outage | Order volume drops > 80% zone-wide for > 20 min | Tech |

> **Trigger #5 is our differentiator.** If Zepto/Blinkit's app itself goes down, riders lose income too. We cover that. No other insurance product does.

**Payout Calculation (per trigger):**
```
Payout = Avg Hourly Earning × Disrupted Hours × Coverage Ratio

Coverage Ratio:  Basic = 60%  |  Standard = 75%  |  Premium = 90%
Disrupted Hours: Trigger start → end timestamps from API data
Avg Hourly Earning: Onboarding-declared, validated against platform order data
```

---

## 🛡️ Layer 5 — Fraud Protection & Security

Every claim passes 3 automated gates before payout is released:

### GPS Validation
- Is the rider's GPS within their registered dark store zone at trigger time?
- Mismatch (rider is outside zone) → claim immediately flagged

### Claims Anomaly Detection (AI)
- Did order volume drop across **all riders** in the zone — or just this one?
- Zone-wide drop = legitimate disruption → proceed
- Solo drop with normal zone activity = high fraud probability → flag
- Isolation Forest scores the anomaly in real-time

### Risk Analytics
- Is the disruption window consistent with the rider's 4-week personal earning baseline?
- Excessive claim frequency vs zone peers → flag
- Cross-reference: was there a verified API event at that exact timestamp + location?

**Decision:**
```
Fraud Score < 0.75  →  Auto-approved  →  Payout initiated  →  UPI credited in <5 min
Fraud Score ≥ 0.75  →  Flagged        →  Admin review queue →  Resolved within 15 min
```

---

## 💰 Layer 6 — Payout System

**Target: Instant Payout within 5 minutes of trigger**

| Channel | Speed | Used When |
|---------|-------|-----------|
| UPI | Instant (< 1 min) | Primary — most riders have UPI |
| Bank Transfer | 1–2 hours | Fallback for riders without UPI |

Powered by **Razorpay Test Mode** (Phases 1–2) → live Razorpay in Phase 3.

Example payout: ₹900 for a Standard plan rider who loses a full shift to heavy rain.

---

## 💸 Weekly Premium Model

| Plan | Premium | Coverage Cap | Payout Ratio | Best For |
|------|---------|-------------|--------------|----------|
| 🟢 Basic Shield | ₹19/week | ₹800/week | 60% | Part-time riders (<4 hrs/day) |
| 🔵 Standard Shield | ₹39/week | ₹1,800/week | 75% | Full-time riders (6–10 hrs/day) |
| 🟣 Premium Shield | ₹79/week | ₹3,500/week | 90% | Power riders (10+ hrs, peak zones) |

Premium recalculated every **Sunday midnight** by Dynamic Pricing AI for the upcoming week.

---

## 🛠️ Full Tech Stack

| Component | Technology |
|-----------|------------|
| Mobile / PWA | React Native Web + Expo |
| Web Admin Dashboard | React.js + Tailwind CSS |
| Maps & Zone Viz | Mapbox GL JS (free tier) |
| Backend API | FastAPI (Python) |
| Auth | Firebase Auth (OTP) |
| Primary Database | PostgreSQL + PostGIS (geospatial zone queries) |
| Cache / Event Queue | Redis (Upstash free tier) |
| ML — Risk & Pricing | XGBoost (Python / scikit-learn) |
| ML — Fraud Detection | Isolation Forest (scikit-learn) |
| ML — Forecasting | Prophet (Meta) |
| Weather Trigger | OpenWeatherMap API (free tier) |
| Heat Trigger | Open-Meteo API (free, no key required) |
| AQI Trigger | WAQI API (free tier) |
| Curfew Trigger | Mock civic alert JSON feed (simulated) |
| Outage Trigger | Simulated platform health API (mock) |
| Payments | Razorpay Test Mode → UPI / Bank Transfer |
| Frontend Hosting | Vercel |
| Backend Hosting | Render (free tier) |
| Database Hosting | Supabase (free tier) |

---

## 📅 6-Week Development Roadmap

### ✅ Phase 1 — Ideation & Foundation (March 4–20)
- [x] Problem statement, persona, and scenario definition
- [x] End-to-end architecture design
- [x] Weekly premium formula and tier structure
- [x] 5 parametric triggers defined
- [x] Full tech stack selected
- [ ] GitHub repository initialized
- [ ] Figma wireframes (rider app + admin dashboard)
- [ ] 2-minute strategy video recorded and uploaded

### 🔨 Phase 2 — Automation & Protection (March 21 – April 4)
- [ ] Rider onboarding and registration (frontend + backend)
- [ ] Policy Engine with dynamic weekly premium calculation
- [ ] 3 live parametric triggers (Rain, Heat, AQI)
- [ ] Claims pipeline (trigger → fraud gate → payout instruction)
- [ ] Razorpay test mode payout integration
- [ ] Rule-based fraud detection v1 (pre-ML)
- [ ] 2-minute demo video

### 🚀 Phase 3 — Scale & Optimise (April 5–17)
- [ ] All 5 parametric triggers live
- [ ] Isolation Forest fraud detection model deployed
- [ ] ShiftGuard Dynamic Pricing AI live end-to-end
- [ ] Sunday Predictive Coverage Advisor (push notifications)
- [ ] Admin insurer dashboard with zone risk heatmap
- [ ] Instant payout simulation (end-to-end UPI flow)
- [ ] 5-minute final walkthrough demo video
- [ ] Final pitch deck (PDF)

---

## 📊 Business Viability

| Metric | Estimate |
|--------|----------|
| Total addressable riders (Zepto + Blinkit, top 10 cities) | ~3,00,000 |
| Year 1 target adoption | 50,000 riders |
| Average weekly premium | ₹45 |
| Weekly premium pool | ₹2.25 Crore/week |
| Target loss ratio | 45–55% (parametric, weather-driven, predictable) |
| Estimated net weekly margin | ~₹11 Lakh/week |

> A consistent 3-star rating across all 3 phases generates DC 82,000 — just enough to break even on the DC 75,000 burn. Our strategy: build for **4–5 star** ratings every phase to accumulate capital, reach Diamond tier, and make DemoJam at DevSummit 2026.

---

## 👥 Team

| Name | Role | University |
|------|------|------------|
| *[Add name]* | *[Add role]* | *[Add university]* |
| *[Add name]* | *[Add role]* | *[Add university]* |
| *[Add name]* | *[Add role]* | *[Add university]* |

---

## 📎 Submission Links

| Item | Link |
|------|------|
| 🎥 Phase 1 Strategy Video (2 min) | *[Add publicly accessible link]* |
| 🖼️ Figma Prototype | *[Add link]* |
| 📦 GitHub Repository | *This repo* |

---

*Built for Guidewire DEVTrails 2026 — Seed. Scale. Soar.*  
*ZeroShield — Because every disrupted hour deserves a safety net.*
