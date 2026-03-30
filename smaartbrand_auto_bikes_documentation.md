# Smaartbrand Auto & Bikes
## Decision Intelligence Platform for Automotive Brands

---

## 1. Executive Summary

Smaartbrand Auto & Bikes is a Multi-Aspect Sentiment Intelligence (MASI) platform that transforms owner feedback from online forums into actionable insights for automotive brand teams. The platform analyzes thousands of owner discussions to surface what buyers love, what needs attention, and how brands compare — all segmented by buyer persona and demographics.

**Core Value Proposition:**
- Turn unstructured owner feedback into department-specific actions
- Benchmark against competitors with aspect-level sentiment scores
- Identify R&D priorities based on real feature requests
- Support multilingual queries (Hindi, German, Danish, Tamil, etc.)

---

## 2. Requirements

### 2.1 Business Requirements

| Requirement | Description |
|-------------|-------------|
| BR-01 | Enable brand teams to understand owner sentiment without manual review reading |
| BR-02 | Provide competitive benchmarking at aspect level (Performance, Safety, Mileage, etc.) |
| BR-03 | Segment insights by buyer persona (value_seeker, enthusiast, family, commuter) |
| BR-04 | Generate actionable recommendations by department (Brand, Marketing, R&D, Service) |
| BR-05 | Support both Cars and Bikes verticals with unified architecture |
| BR-06 | Enable natural language queries in multiple languages |

### 2.2 Functional Requirements

| Requirement | Description |
|-------------|-------------|
| FR-01 | Dashboard with brand/segment filtering |
| FR-02 | Drivers tab showing strengths and concerns with sample reviews |
| FR-03 | Satisfaction tab with aspect-level breakdown and comparison |
| FR-04 | R&D Signals tab with feature requests from owner discussions |
| FR-05 | Demographics tab with persona and gender distribution |
| FR-06 | AI Chat for natural language queries with exact data citations |
| FR-07 | Model vs Model comparison with specs and sentiment |
| FR-08 | Export/sharing capabilities for reports |

### 2.3 Non-Functional Requirements

| Requirement | Description |
|-------------|-------------|
| NFR-01 | Response time < 3 seconds for dashboard loads |
| NFR-02 | Chat response time < 10 seconds |
| NFR-03 | Support 50+ concurrent users |
| NFR-04 | 99.9% uptime (Railway deployment) |
| NFR-05 | Data refresh: batch updates (not real-time) |
| NFR-06 | GDPR compliant — no PII stored |

---

## 3. Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │   Cars App      │  │   Bikes App     │  │   Future Apps   │     │
│  │  (Railway)      │  │  (Railway)      │  │                 │     │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘     │
└───────────┼─────────────────────┼───────────────────────────────────┘
            │                     │
            ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Backend                           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │
│  │  │ /api/    │ │ /api/    │ │ /api/    │ │ /api/    │        │   │
│  │  │ aspects  │ │ reviews  │ │ rd-      │ │ chat     │        │   │
│  │  │          │ │          │ │ insights │ │          │        │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│              VEHICLE_TYPE env var (car / bike)                     │
│              Controls: CAR_% or BIKE_% prefix filtering            │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Google BigQuery                             │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │   │
│  │  │product_master│ │   reviews    │ │   aspects    │         │   │
│  │  │  (specs)     │ │  (verbatims) │ │ (sentiment)  │         │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘         │   │
│  │  ┌──────────────┐ ┌──────────────┐                          │   │
│  │  │ rd_insights  │ │    views     │                          │   │
│  │  │ (features)   │ │ (car/bike)   │                          │   │
│  │  └──────────────┘ └──────────────┘                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       AI/ML LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Gemini Data Analytics Agent                     │   │
│  │         agent_2ec1baf1-c0b3-47cb-acff-72bc0d34c930          │   │
│  │                                                              │   │
│  │  • Receives pre-fetched data from BigQuery                  │   │
│  │  • Uses exact numbers (no hallucination)                    │   │
│  │  • Generates department-specific insights                   │   │
│  │  • Supports multilingual responses                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│  Reddit    │───▶│  DataFor   │───▶│   MASI     │───▶│  BigQuery  │
│  Forums    │    │  SEO API   │    │ Extraction │    │  Tables    │
└────────────┘    └────────────┘    └────────────┘    └────────────┘
                                                             │
                                                             ▼
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│  Dashboard │◀───│  FastAPI   │◀───│  BigQuery  │◀───│   Views    │
│    UI      │    │  Backend   │    │  Client    │    │ (filtered) │
└────────────┘    └────────────┘    └────────────┘    └────────────┘
      │
      ▼
┌────────────┐    ┌────────────┐    ┌────────────┐
│   Chat     │───▶│ Pre-fetch  │───▶│   Data     │
│  Query     │    │  BQ Data   │    │   Agent    │
└────────────┘    └────────────┘    └────────────┘
```

### 3.3 Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML5, TailwindCSS, ApexCharts, Marked.js |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | Google BigQuery |
| AI/Chat | Gemini Data Analytics Agent |
| Deployment | Railway (Docker containers) |
| Data Source | Reddit (r/CarsIndia, r/indianbikes) via DataForSEO |

---

## 4. Features

### 4.1 Dashboard Features

| Feature | Description |
|---------|-------------|
| **Brand Selector** | Filter by brand (Maruti, Tata, Hyundai, Royal Enfield, etc.) |
| **Segment Filter** | Filter by vehicle segment (SUV, Sedan, Hatchback, Cruiser, etc.) |
| **Stats Row** | Total mentions, top strength, needs attention, top buyer type |
| **Drivers Tab** | What Buyers Love / What Needs Attention with clickable review counts |
| **Satisfaction Tab** | Aspect breakdown table + brand comparison chart |
| **R&D Signals Tab** | Feature requests extracted from owner discussions |
| **Demographics Tab** | Persona distribution (value_seeker, enthusiast, etc.) + gender split |

### 4.2 Chat Features

| Feature | Description |
|---------|-------------|
| **Natural Language** | Ask questions in plain English, Hindi, German, Danish, etc. |
| **Brand Analysis** | "How is Tata doing?" → Full insight with actions |
| **Comparisons** | "Compare Maruti vs Hyundai" → Side-by-side with exact numbers |
| **Model vs Model** | "Compare Seltos vs Creta" → Specs table + sentiment |
| **Aspect Deep-Dive** | "How is Honda doing on Mileage?" → Focused analysis |
| **SEO FAQs** | "Maruti FAQs" → Q&A format for website content |
| **Ad Copy** | "Ad copy for Kia" → PROMOTE/AVOID recommendations |
| **Multilingual** | Responds in the same language as the query |

### 4.3 Key Metrics

| Metric | Formula | Usage |
|--------|---------|-------|
| **Satisfaction %** | positive / (positive + negative) × 100 | Fair comparison across volumes |
| **Positive Count** | SUM(sentiment = 1) | Raw positive mentions |
| **Negative Count** | SUM(sentiment = -1) | Raw negative mentions |
| **Total Mentions** | positive + negative | Discussion volume / mindshare |

---

## 5. Database Schema

### 5.1 Tables

#### product_master
Product specifications and metadata.

| Column | Type | Description |
|--------|------|-------------|
| product_id | STRING | Primary key (CAR_brand_model or BIKE_brand_model) |
| vehicle_type | STRING | "car" or "bike" |
| brand | STRING | Brand name (Maruti, Tata, Royal Enfield, etc.) |
| model | STRING | Model name (Swift, Nexon, Classic 350, etc.) |
| segment | STRING | Vehicle segment (SUV, Sedan, Cruiser, etc.) |
| price_range_lakh | STRING | Price range in lakhs (e.g., "10-15") |
| engine_cc | INT64 | Engine displacement in cc |
| fuel_type | STRING | Petrol, Diesel, Electric, Hybrid |
| power_hp | INT64 | Power output in horsepower |
| mileage_kmpl | FLOAT64 | Claimed mileage in kmpl |

#### reviews
Raw review data with MASI extractions.

| Column | Type | Description |
|--------|------|-------------|
| review_id | STRING | Primary key |
| product_id | STRING | Foreign key to product_master |
| brand | STRING | Brand name |
| model | STRING | Model name |
| segment | STRING | Vehicle segment |
| comment_body | STRING | Full review text |
| subreddit | STRING | Source subreddit |
| author | STRING | Reddit username (anonymized) |
| score | INT64 | Reddit score |
| created_date | DATE | Review date |
| gender | STRING | M (Male), F (Female), U (Unknown) |
| masi_persona | STRING | Extracted persona |
| masi_intent | STRING | Purchase intent |
| masi_overall | STRING | Overall sentiment |
| masi_features_sought | STRING | Features mentioned |
| masi_budget_lakhs | FLOAT64 | Budget mentioned |
| masi_location | STRING | Location mentioned |

#### aspects
Aspect-level sentiment data.

| Column | Type | Description |
|--------|------|-------------|
| aspect_id | STRING | Primary key |
| product_id | STRING | Foreign key to product_master |
| brand | STRING | Brand name |
| model | STRING | Model name |
| aspect | STRING | Aspect name (Performance, Safety, Mileage, etc.) |
| sentiment | INT64 | 1 (positive) or -1 (negative) |
| persona | STRING | Buyer persona |
| intent | STRING | Purchase intent |
| gender | STRING | M, F, or U |
| location | STRING | Location mentioned |
| features_sought | STRING | Features mentioned |
| budget_lakhs | FLOAT64 | Budget mentioned |

#### rd_insights
R&D signals and feature requests.

| Column | Type | Description |
|--------|------|-------------|
| insight_id | STRING | Primary key |
| product_id | STRING | Foreign key to product_master |
| brand | STRING | Brand name |
| model | STRING | Model name |
| persona | STRING | Buyer persona |
| intent | STRING | Purchase intent |
| location | STRING | Location mentioned |
| features_sought | STRING | Pipe-separated feature list |
| mileage_expected | FLOAT64 | Expected mileage |
| budget_lakhs | FLOAT64 | Budget mentioned |

### 5.2 Views

| View | Description |
|------|-------------|
| reviews_cars | Reviews filtered to CAR_% products |
| reviews_bikes | Reviews filtered to BIKE_% products |
| aspects_cars | Aspects filtered to CAR_% products |
| aspects_bikes | Aspects filtered to BIKE_% products |
| rd_insights_cars | R&D insights filtered to CAR_% products |
| rd_insights_bikes | R&D insights filtered to BIKE_% products |
| brand_summary | Aggregated brand-level satisfaction |
| aspect_summary | Aggregated aspect-level satisfaction |

### 5.3 Aspect Mapping

| Aspect | Icon | Description |
|--------|------|-------------|
| Performance | 🏎️ | Engine power, acceleration, driving dynamics |
| Comfort | 🛋️ | Ride quality, seating, NVH |
| Safety | 🛡️ | Safety features, crash ratings, ADAS |
| Features | ⚙️ | Technology, infotainment, convenience |
| Space | 📦 | Cabin space, boot space, legroom |
| Mileage | ⛽ | Fuel efficiency, range |
| Ownership | 🔧 | Maintenance, service costs, reliability |
| Value | 💰 | Value for money, pricing |
| Brand | ⭐ | Brand perception, resale value |
| Style | 🎨 | Design, looks, aesthetics |
| Handling | 🎯 | Steering, cornering, stability |
| Build | 🔩 | Build quality, fit and finish |

### 5.4 Persona Mapping

| Persona | Description |
|---------|-------------|
| value_seeker | Budget-conscious, focused on value for money |
| enthusiast | Performance-focused, interested in specs and driving experience |
| family | Safety and space-focused, practical considerations |
| commuter | Daily driving focus, mileage and reliability |
| first_buyer | New buyers, often comparing multiple options |
| tech | Feature-focused, interested in technology and gadgets |

---

## 6. Chat Prompt (Data Agent)

The following prompt is used to configure the Gemini Data Analytics Agent:

```
You are SmaartAnalyst, an automotive decision intelligence assistant powered by Smaartbrand.

=== CRITICAL: USE PROVIDED DATA EXACTLY ===
I am providing you with EXACT data from our database. 
DO NOT modify, round differently, or invent any numbers.
USE THE EXACT PERCENTAGES AND COUNTS PROVIDED BELOW.
If data is not provided, query the database using the schema below — no hallucination.
Round percentages to whole numbers (72.3% → 72%).
Never cite exact review counts — say "based on owner feedback" instead.

=== LANGUAGE RULES ===
Always respond in the SAME LANGUAGE as the user's question.
Keep technical terms (brand names, aspect names, percentages) in English for clarity.

=== VOLUME THRESHOLDS ===
- Only cite aspects with 100+ mentions as primary insights
- For aspects with <100 mentions, caveat: "based on limited feedback"
- Never lead with low-volume aspects (even if 100% satisfaction)

=== RESPONSE FORMAT ===

📊 **Insight**: [2-3 sentences with specific % scores]

👥 **Buyer Mix**: [value_seeker X%, enthusiast Y%, family Z%]

🎯 **Actions by Department**:

👔 Brand Manager: [positioning + segment targeting]

📢 Marketing: 
   ✓ PROMOTE: [aspects where you win]
   ✗ AVOID: [aspects where competitor wins]

🔬 R&D / Product: [feature requests from data]

🔧 Service: [if Ownership issues in data]

=== QUERY-SPECIFIC FORMATS ===

**FAQs** → Q&A format only, no Actions
**Compare Model vs Model** → Specs table + sentiment table + Actions
**Compare Brand vs Brand** → Aspect comparison + Actions
**Ad Copy** → PROMOTE/AVOID focus + Actions

=== ANTI-HALLUCINATION RULES ===
1. Answer ONLY from data in the tables
2. NEVER invent scores or rankings
3. If data missing, say "data not available"
4. PREFER "I don't know" over making up an answer
```

See `auto_data_agent_prompt_v2.md` for the complete prompt.

---

## 7. Sample Chat Queries

### 7.1 Brand Analysis

**Query:** "How is Tata doing on Safety?"

**Response:**
```
📊 Insight: Tata Safety 🛡️ satisfaction is 46%, based on owner feedback. 
This trails behind Comfort 🛋️ (63%) and Mileage ⛽ (60%), indicating 
a perception gap despite Tata's safety marketing focus.

👥 Buyer Mix: value_seeker 30%, commuter 24%, enthusiast 13%, family 10%

🎯 Actions by Department:

👔 Brand Manager: Address the 46% Safety perception gap — it contradicts 
brand positioning as a safety leader.

📢 Marketing: 
   ✓ PROMOTE: Comfort (63%) and Mileage (60%) as primary USPs
   ✗ AVOID: Safety claims until perception improves

🔬 R&D: Investigate specific safety concerns in negative reviews.
```

### 7.2 Comparison

**Query:** "Compare Maruti vs Hyundai"

**Response:**
```
📊 Insight: Maruti leads with 58% overall satisfaction vs Hyundai at 56%. 
Maruti wins on Mileage ⛽ (66% vs 61%) while Hyundai leads on Features ⚙️ 
(65% vs 64%) and Safety 🛡️ (58% vs 54%).

👥 Buyer Mix: value_seeker 31%, commuter 25%, enthusiast 12%

🎯 Actions by Department:

👔 Brand Manager (Maruti): Defend mileage leadership against Hyundai.

📢 Marketing (Hyundai): 
   ✓ PROMOTE: Features and Safety advantages
   ✗ AVOID: Mileage comparisons with Maruti
```

### 7.3 FAQs

**Query:** "Maruti FAQs"

**Response:**
```
📝 Maruti FAQs

Q: How do owners rate Maruti's mileage?
A: Maruti achieves 66% satisfaction on Mileage ⛽, based on owner feedback.

Q: Is Maruti reliable?
A: Yes, Reliability scores 77% satisfaction — one of the brand's top strengths.

Q: What are the main concerns with Maruti?
A: Brand perception (50%) and Safety 🛡️ (54%) are the lowest-rated aspects.

Q: Who buys Maruti cars?
A: Primarily Value Seekers (33%) and Commuters (24%).
```

### 7.4 Multilingual

**Query:** "मारुति और टाटा की तुलना करें" (Hindi)

**Response:**
```
📊 Insight: मारुति 58.2% संतुष्टि के साथ टाटा (46.9%) से आगे है। 
टाटा में नकारात्मक फीडबैक सकारात्मक से अधिक है।

👥 Buyer Mix: value_seeker 30%, commuter 24%, enthusiast 14%

🎯 Actions by Team:

👔 Brand Manager (Tata): ब्रांड धारणा सुधारने पर ध्यान दें।

📢 Marketing (Maruti): 58% संतुष्टि दर को मुख्य USP बनाएं।
```

---

## 8. Deployment

### 8.1 Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| VEHICLE_TYPE | "car" or "bike" | car |
| GCP_PROJECT | GCP project ID | gen-lang-client-0143536012 |
| GCP_CREDENTIALS_JSON | Base64 encoded service account JSON | eyJhbGci... |
| BQ_DATASET | BigQuery dataset | auto |

### 8.2 Railway Deployments

| App | URL | VEHICLE_TYPE |
|-----|-----|--------------|
| Smaartbrand Cars | smaartbrand-auto.up.railway.app | car |
| Smaartbrand Bikes | smaartbrand-bikes.up.railway.app | bike |

### 8.3 Files

| File | Description |
|------|-------------|
| main.py | FastAPI backend with all API endpoints |
| index.html | Single-page dashboard UI |
| requirements.txt | Python dependencies |
| Dockerfile | Container configuration |
| railway.json | Railway deployment config |

---

## 9. Future Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 1 | Cars + Bikes dashboards | ✅ Complete |
| Phase 2 | AI Chat with Data Agent | ✅ Complete |
| Phase 3 | Model vs Model specs comparison | 🔄 In Progress |
| Phase 4 | Region filter (India/US) | 📋 Planned |
| Phase 5 | Export to PDF/PPT | 📋 Planned |
| Phase 6 | Scheduled email reports | 📋 Planned |
| Phase 7 | API access for enterprise | 📋 Planned |

---

## 10. Support

**Product:** Smaartbrand Auto & Bikes  
**Company:** Acquink Technologies  
**Contact:** [Giri - CEO]  
**Website:** acquink.com

---

*Document Version: 1.0*  
*Last Updated: March 30, 2026*
