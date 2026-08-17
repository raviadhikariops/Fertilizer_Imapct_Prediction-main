# AgriNexus Project Flow Diagram

## 1. High-Level AgriNexus Project Flow

```mermaid
flowchart TD
    U[User] --> B[Web Browser]
    B --> R[Flask Routes]

    R --> A[Authentication & Session]
    A --> DB[(SQLite Database)]

    R --> Y[Yield Planner]
    Y --> L[Local Scoring]
    Y --> FERT[Fertilizer Plan]
    Y --> CROP[Crop Recommendations]
    L --> DB
    FERT --> DB
    CROP --> DB

    R --> C[Crop Advisor]
    C --> CS[Crop Similarity Engine]
    CS --> ML1[ML Crop Ranking]
    CS --> AI1[Gemini / Groq Advice]

    R --> F[Fertilizer Advisor]
    F --> FS[Fertilizer Matching]
    FS --> ML2[ML Fertilizer Recommendation]
    FS --> AI2[Gemini / Groq Guidance]

    R --> D[Crop Disease Detection]
    D --> IMG[Upload Leaf Image]
    IMG --> DL[Deep Learning Model]
    DL --> DIAG[Disease Diagnosis]
    DIAG --> TREAT[Treatment + Fertilizer Advice]

    R --> H[Chatbot]
    H --> CTX[Saved Field Context]
    H --> AI3[Gemini / Groq Response]

    R --> P[Prediction History & Export]
    P --> DB
    P --> CSV[CSV Export]

    ML1 --> UI[User Results Page]
    AI1 --> UI
    ML2 --> UI
    AI2 --> UI
    DIAG --> UI
    AI3 --> UI
```

## 2. Detailed AgriNexus System Architecture

```mermaid
flowchart LR
    subgraph Client
        Browser[Browser / UI]
        Templates[Jinja Templates]
    end

    subgraph Server
        Flask[Flask App - app.py]
        Auth[Auth + Session Management]
        Routes[Route Handlers]
        DBLayer[SQLite DB Helper Layer]
        AI[AI Orchestration Layer]
        ML[ML Inference Layer]
        DL[Deep Learning Inference]
    end

    subgraph Data
        SQLite[(SQLite DB)]
        CSVData[CSV Datasets]
        Models[Model Artifacts]
        Env[.env / Config]
    end

    Browser --> Templates
    Templates --> Flask
    Flask --> Routes
    Routes --> Auth
    Routes --> DBLayer
    Routes --> AI
    Routes --> ML
    Routes --> DL

    Auth --> SQLite
    DBLayer --> SQLite
    AI --> Env
    ML --> CSVData
    ML --> Models
    DL --> Models
    AI --> External[Gemini / Groq APIs]
```

## 3. AgriNexus System Component Diagram

```mermaid
flowchart TB
    subgraph Client
        UI[Web Browser]
        Templates[Jinja2 Templates]
    end

    subgraph Application
        Server[Flask Server (app.py)]
        Routes[Route Handlers]
        Auth[Auth & Session Manager]
        Yield[Yield Planner]
        Crop[Crop Advisor]
        Fert[Fertilizer Advisor]
        Disease[Crop Disease Detector]
        Chat[AI Chatbot]
        History[Prediction History / Export]
    end

    subgraph Services
        ML[ML Model Inference]
        DL[Deep Learning Inference]
        AI[AI / Gemini / Groq]
    end

    subgraph Storage
        DB[(SQLite)]
        Data[CSV Dataset Files]
        ModelFiles[Saved Model Files]
        Config[.env / Secrets]
    end

    UI --> Templates
    Templates --> Server
    Server --> Routes
    Routes --> Auth
    Routes --> Yield
    Routes --> Crop
    Routes --> Fert
    Routes --> Disease
    Routes --> Chat
    Routes --> History

    Yield --> ML
    Yield --> Data
    Crop --> ML
    Fert --> ML
    Disease --> DL
    Chat --> AI

    Auth --> DB
    Yield --> DB
    Crop --> DB
    Fert --> DB
    Disease --> DB
    Chat --> DB
    History --> DB

    ML --> ModelFiles
    DL --> ModelFiles
    AI --> Config
```

## 4. AgriNexus Database Entity Relationship Diagram

```mermaid
erDiagram
    users {
        integer id PK
        text username
        text email
        text password_hash
        datetime created_at
    }

    predictions {
        integer id PK
        integer user_id FK
        text soil
        text weather
        text fertilizer
        real amount
        text crop
        real predicted_yield
        text description
        text raw_response
        text prediction_type
        real nitrogen
        real phosphorus
        real potassium
        real ph
        real temperature
        real humidity
        real rainfall
        real moisture
        text risk_level
        real confidence
        text recommendation
        datetime created_at
    }

    chat_messages {
        integer id PK
        integer user_id FK
        text role
        text content
        text provider
        datetime created_at
    }

    users ||--o{ predictions : saves
    users ||--o{ chat_messages : owns
```

## 5. AgriNexus User Journey

```mermaid
flowchart TD
    Start[Open App] --> Home[Home Page]
    Home --> Login{Logged In?}
    Login -- No --> Register[Register / Login]
    Register --> Dashboard[User Dashboard]
    Login -- Yes --> Dashboard

    Dashboard --> Yield[Use Yield Planner]
    Dashboard --> CropRec[Open Crop Advisor]
    Dashboard --> FertRec[Open Fertilizer Advisor]
    Dashboard --> Disease[Upload Disease Image]
    Dashboard --> Chat[Open AI Chatbot]

    Yield --> Save[Save Prediction]
    CropRec --> ViewCrop[View Ranked Crops]
    FertRec --> ViewFert[View Fertilizer Plan]
    Disease --> ViewDisease[See Disease + Treatment]
    Chat --> ContinueChat[Continue Conversation]

    Save --> History[View Prediction History]
    History --> Export[Export CSV]
    History --> Detail[Open Prediction Details]
```

## 6. AI/ML Prediction Workflow

```mermaid
flowchart TD
    User[User submits field inputs] --> Web[Web Form / API Request]
    Web --> Server[Flask Route receives request]
    Server --> Validate[Validate and normalize inputs]
    Validate --> MLInput[Build ML feature vector]
    MLInput --> CropModel[Crop recommendation model]
    MLInput --> FertModel[Fertilizer recommendation model]
    CropModel --> CropResult[Ranked crop recommendations]
    FertModel --> FertResult[Recommended fertilizer]
    CropResult --> AIExplain[AI explanation / guidance]
    FertResult --> AIExplain
    AIExplain --> Response[Render result page / JSON response]
    Response --> Save[Optionally save prediction]
    Save --> DB[(SQLite)]
```

## 7. Disease Detection Workflow

```mermaid
flowchart TD
    User[User uploads leaf image] --> Web[Crop disease page]
    Web --> Server[Flask route receives file]
    Server --> ImageProcess[Preprocess image]
    ImageProcess --> DLModel[Load crop-specific DL model]
    DLModel --> Prediction[Disease class prediction]
    Prediction --> Treatment[Generate treatment guidance]
    Treatment --> AIAdvice[AI / Gemini / Groq enrichment]
    AIAdvice --> Result[Render disease diagnosis page]
    Result --> Save[Optionally save prediction / history]
    Save --> DB[(SQLite)]
```

## 8. Prediction History and CSV Export Workflow

```mermaid
flowchart TD
    User[User opens history page] --> Server[History route]
    Server --> Query[Query saved predictions]
    Query --> DB[(SQLite)]
    DB --> Records[Retrieve prediction records]
    Records --> Page[Render history HTML]
    Page --> User

    User --> ExportBtn[Clicks export CSV]
    ExportBtn --> CSVRoute[Export route handler]
    CSVRoute --> Read[Read prediction records]
    Read --> Writer[Format CSV file]
    Writer --> Download[Send CSV download response]
    Download --> User
```
