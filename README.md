<div align="center">

# 🌐 Data Science & AI Portfolio

### Álvaro Moctezuma · Data Governance Engineer · Big Data & Data Science

*Behavior prediction · Evolutionary AI · Computer vision · Data governance · Process automation*

<p>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenGL-moderngl-5586A4?style=for-the-badge&logo=opengl&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
</p>
<p>
  <img src="https://img.shields.io/badge/Projects-80+-orange?style=flat-square&logo=github" />
  <img src="https://img.shields.io/badge/AI%20Lab-22%20simulators-8A2BE2?style=flat-square" />
  <img src="https://img.shields.io/badge/Governance-19%20frameworks-2E8B57?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" />
</p>

**[🧪 AI Lab](#-ai-lab--simulators-games--computer-vision)** ·
**[🛡️ Governance](#%EF%B8%8F-data-governance--integrity-frameworks)** ·
**[🤖 GenAI](#-generative-ai--llms)** ·
**[⚙️ MLOps](#%EF%B8%8F-mlops--data-architecture)** ·
**[📈 ML](#-machine-learning--business-analytics)** ·
**[🧬 Health](#-health--life-sciences)** ·
**[🧰 Stack](#-tech-stack)** ·
**[📫 Contact](#-contact--connect)**

</div>

---

## 🗺️ Welcome | Willkommen | ברוכים הבאים | Benvenuto

| 🇬🇧 English | 🇩🇪 Deutsch | 🇮🇱 עברית | 🇱🇺 Lëtzebuergesch |
| :--- | :--- | :--- | :--- |
| Welcome to my official portfolio. I specialize in behavior prediction, automation, and smart data analysis. | Willkommen in meinem Portfolio. Ich spezialisiere mich auf Verhaltensvorhersage und Prozessautomatisierung. | ברוכים הבאים לתיק העבודות הרשמי שלי. אני מתמחה בחיזוי התנהגות ובאוטומציה של תהליכים. | Wëllkomm op mengem Portfolio. Ech si spezialiséiert op Verhalensvirhersage an Automatiséierung vu Prozesser. |

| 🇮🇹 Italiano | 🇫🇷 Français | 🇪🇸 Español |
| :--- | :--- | :--- |
| Benvenuto nel mio portfolio. Sono specializzato nella previsione dei comportamenti e nell’automazione dei processi. | Bienvenue dans mon portfolio. Je suis spécialisé dans la prédiction du comportement et l’automatisation des processus. | Bienvenido a mi portafolio. Me especializo en predicción de comportamiento y automatización de procesos. |

---

## 🧪 AI Lab — Simulators, Games & Computer Vision

> 22 desktop projects written from scratch in Python: agents that **learn by evolution**, physics simulators,
> real-map defense systems, 3D flight, a hand-written emulator core and **Kinect-based** clinical tools.
> Every project has its own README (in Spanish) and a one-click `.bat` launcher.
> Training data, recordings and map caches are generated locally and are not versioned.

### 🎮 Evolutionary agents in original games

| Project | What the AI learns | Method | Stack |
| :--- | :--- | :--- | :--- |
| 🐍 [Snake](SnakeEvolutivo) | A population of 200 snakes learns to eat and survive across 8 levels | Neural nets + evolution strategy | `numpy` `tkinter` |
| 🧱 [Tetris](TetrisEvolutivo) | Weighs 8 board features to place every piece; learns from your games too | CMA-ES + imitation | `numpy` `tkinter` |
| 👻 [Maze chaser (NN)](PacManEvolutivo) | Clears generated mazes while avoiding ghosts, 8 levels | Neural net + evolution strategy | `numpy` `pygame` |
| 🌳 [Maze chaser (GP)](PacManEvolutivoGP) | Same game, but the brain is an evolved program tree | Genetic programming | `numpy` `pygame` |
| 🏎️ [Road racer](RoadFighterEvolutivo) | Reaches the finish line dodging traffic, guided by a teacher | Recurrent net + ES + teacher | `numpy` `pygame` |
| 🏎️ [Road racer 0](RoadFighterEvolutivo0) | Same game, learning from zero | Evolution strategy | `numpy` `pygame` |
| 🏎️ [Road racer 2](RoadFighterEvolutivo2) | Same game, learning by reinforcement | PPO | `numpy` `pygame` |
| ✈️ [Vertical shooter](1942Evolutivo) | Pilots a fighter through 8 missions; can imitate the player | Neural net + ES + imitation | `numpy` `tkinter` |
| 🔫 [Run & gun](ContraEvolutivo) | Runs, jumps and shoots through 8 stages, 1 or 2 trainable players | Multiprocess ES | `numpy` `tkinter` |

### 🚗 Physics, vehicles & flight

| Project | Description | Stack |
| :--- | :--- | :--- |
| 🏍️ [Autonomous motorcycle](MotoTerminator) | Rider-less robot motorcycle that learns to balance (gyroscope) and ride real city streets; test suite included | `numpy` `numba` `tkinter` |
| 🅿️ [Parking](EstacionamientoEvolutivo) | Genetic algorithm that plans forward / reverse parking maneuvers — pure standard library | `tkinter` |
| 🚛 [Tractor-trailer parking](EstacionamientoTrailer) | Same idea with 1 or 2 trailers and variable bay sizes | `tkinter` |
| 🚁 [Delivery drone](DronEntregas) | Medicine-delivery drone (multirotor & fixed wing) over real OpenStreetMap cities | `tkinter` `Pillow` |
| 🛩️ [F-15 flight](F15Evolutivo) | 3D cockpit simulator: radar, cold & dark start-up, JSON missions and a learning curriculum | `moderngl` `pygame` |
| ✨ [Drone light show](EspectaculoDrones) | Designer for text / image / 3D formations, Hungarian assignment and CSV export | `moderngl` `scipy` |
| ⛏️ [Mining drones](MineriaDrones) | Survey planning, LiDAR / 3D, A/B comparison against authorized zones, thermal & visual inspection | `moderngl` `matplotlib` |

### 🛡️ Defense simulations on real maps

| Project | Description | Stack |
| :--- | :--- | :--- |
| 🎯 [Mobile Defense Dome](DomoDefensa) | Mobile anti-air batteries (1–8 launchers) with a trainable fire-control AI on satellite / hybrid / street maps | `pygame` `numpy` |
| 🌍 [Global Shield](EscudoGlobal) | Worldwide version: boost / exo / high / terminal layers, multiple warheads and decoys | `pygame` `numpy` |

### 👁️ Computer vision, hardware & health

| Project | Description | Stack |
| :--- | :--- | :--- |
| 🚦 [Kinect Distance](KinectDistancia) | Proximity traffic light with a custom Kinect USB driver: color + infrared, tracking and approach speed | `libusb` `opencv` |
| 🦴 [OrtoKinect](OrtoKinect) | Orthopedics & rehab assessment: goniometry, balance, gait, sit-to-stand, patient records and PDF reports | `mediapipe` `reportlab` |
| 🩺 [Fatty-liver AI](higado_graso_ia) | Grades hepatic steatosis (S0–S3) on B-mode ultrasound with Grad-CAM; trained model included | `PyTorch` `scikit-learn` |
| 🕹️ [GBC emulator + AI](EmuladorGBC) | Game Boy / Game Boy Color emulator core accelerated with numba, with an AI player and checkpoints (no ROMs included) | `numba` `numpy` |

---

## 🛡️ Data Governance & Integrity Frameworks

| | Project | | Project |
| :---: | :--- | :---: | :--- |
| 🏛️ | [Enterprise Data Governance: Quality & Integrity Audit](enterprise-data-governance-framework) | 📑 | [Governance Audit & Regulatory Compliance (2005-2021)](high-level-governance-audit) |
| 📦 | [Tesla Supply Chain Data Integrity (SC-DIG)](tesla-supply-chain-governance) | 🏦 | [EuroWealth Dynamics: Socio-Economic Governance](eurowealth-dynamics-governance) |
| 🛒 | [Amazon Sales Strategic Insights (2005-2021)](amazon-sales-governance) | 🎵 | [Spotify Metadata Integrity & Governance](spotify-metadata-governance) |
| 🏥 | [BlueShield Governance Framework](blueshield-governance-framework) | ✈️ | [AeroGovernance Pro: Strategic Analytics](aerogovernance-pro) |
| 🔗 | [Enterprise Data Lineage & Integrity](enterprise-data-lineage) | 📈 | [Project Phoenix: Revenue Growth Management](project-phoenix-governance) |
| 🛡️ | [Data Shield Compliance Suite](data-shield-compliance) | 🕵️ | [Project Sentinel: Data Anonymization Engine](project-sentinel) |
| ⚡ | [Enterprise Energy Metadata & Lineage](enterprise-energy-metadata) | 💎 | [Governance & Data Quality Assurance (AG-DQA)](advanced-governance-dqa) |
| 🧹 | [Automated Data Cleaning Pipeline](automated-data-cleaning-governance) | 👁️ | [Data Observability & Risk Assessment](enterprise-data-observability) |
| 🥇 | [Enterprise MDM & Golden Record Resolution](enterprise-mdm-golden-record) | 📉 | [Employee Promotion Prediction with AutoML](employee-promotion-automl) |
| 🔄 | [Data Governance & Versioning (DVC)](data-governance-versioning) | | |

---

## 🤖 Generative AI & LLMs

* 🧠 [Text generation system using Transformer models](modular-ai-framework)
* 🎨 [GAN implementation for synthetic image generation](gan-image-generator)
* ✍️ [Personalized text generation system (LLM)](llm-text-generator)
* 📝 [GPT-2 / T5 creative text generation](text-generation-gpt2)

## ⚙️ MLOps & Data Architecture

* 🚀 [ML classification model deployed as a REST API (FastAPI)](classification-api-fastapi)
* 🔄 [Full CI/CD pipeline for ML projects](ml-cicd-pipeline)
* 🐳 [Scalable inference system with Docker Compose](scalable-inference-system)
* 📡 [ML API with documented OpenAPI endpoints](ml-api-collaboration)
* 🔄 [Scalable data ingestion & transformation pipeline](scalable-ingestion-pipeline)
* 🧩 [Unified data architecture with ETL and stream processing](unified-data-architecture)
* 🧠 [Modular automation framework for workflow optimization](modular-automation-framework)

## 📈 Machine Learning & Business Analytics

| Prediction & risk | Customers & retail | Methods & tooling |
| :--- | :--- | :--- |
| 🔄 [Churn prediction](churn-prediction) | 👥 [Customer segmentation (K-Means)](customer-segmentation) | 🔬 [GridSearchCV classification pipeline](classification-gridsearch-notebook) |
| 📉 [Churn survival analysis](churn-survival-analysis) | 💎 [Customer lifetime value](clv-prediction-model) | 📊 [Classifier comparison (RandomizedSearch)](model-comparison-randomizedsearch) |
| 💰 [Credit risk scoring](credit-risk-model) | 🛍️ [Product recommendation engine](product-recommendation) | 📌 [LightGBM + Optuna tuning](lgbm-optuna-hyperparameter-tuning) |
| 🔐 [Fraud detection](fraud-detection-system) | 💲 [Dynamic pricing](dynamic-pricing-model) | 🧠 [Supervised learning engine](supervised-learning-engine) |
| 🔍 [Profile-based inference engine](profile-inference-engine) | 📦 [Supply chain demand sensing](supply-chain-demand-sensing) | 🤖 [Adaptive simulation framework](adaptive-simulation-framework) |
| 📈 [Time-series forecasting](timeseries-forecasting-model) | 📊 [BI dashboard (R Shiny)](business-intelligence-dashboard) | 📊 [Multidimensional analytics](multidimensional-analytics-system) |
| | 📉 [Churn & recommendation collaboration](churn-collaboration-project) | 📌 [Product · DS · Engineering collaboration](collaborative-ml-project) |

## 🔍 NLP

* 🗣️ [Sentiment analysis (NLP)](sentiment-analysis-nlp) · 💬 [Sentiment engine for customer reviews](sentiment-analysis-engine)
* 🏷️ [Named Entity Recognition](ner-specialized-nlp) · 📚 [Multiclass text classification](text-multiclass-classifier)
* 🎬 [Content analysis & classification: Netflix insights](Content_Analysis_and_Classification)

## 🧬 Health & Life Sciences

* 🧬 [Lupus (SLE): immunological intervention simulation](LUPUS)
* 🧬 [Gene expression analysis pipeline in R](gene-expression-pipeline)
* 🧪 [Molecular modeling for gene-editing therapy simulation](molecular-modeling-tool)
* 🩺 [Fatty-liver ultrasound AI](higado_graso_ia) · 🦴 [OrtoKinect rehab assessment](OrtoKinect)

## 📡 IoT & Edge Computing

* 🌡️ [Environmental monitoring with embedded ML](environmental-monitoring-system)
* 📈 [IoT anomaly detection dashboard](iot-anomaly-detection)
* 📟 [Edge computing on Raspberry Pi](edge-computing-raspberrypi)
* 🔥 [Smart fire suppression network prototype](smart-fire-suppression-network)

## 🏛️ Legacy & Core Systems

* `COBOL` [Payroll management for small businesses](payroll-cobol-system) · `COBOL` [Retail inventory management](inventory-management-cobol)
* `C` [Contact agenda](contact-agenda-c) · `C` [ATM simulator](atm-simulator-c)

---

## 🔭 Research Roadmap

> **🛰️ Remote Sensing Data Pipeline for Environmental AI** — satellite and drone imagery to detect deforestation, soil degradation and water stress.
> `Remote Sensing` · `Geospatial Analysis` · `Computer Vision` · `Earth Observation`

> **🏥 AI-Driven Clinical Decision Support** — patient-data analysis to predict complications and recommend evidence-based interventions.
> `Electronic Health Records` · `Predictive Modeling` · `Risk Stratification` · `Medical AI`

> **📦 Demand Forecasting for Supply Chain Optimization** — high-precision demand prediction for inventory, transport allocation and cost reduction.
> `Time Series` · `XGBoost` · `Optimization` · `Business Intelligence`

> **🧠 Ethical AI Governance Dashboard** — audit and simulate algorithmic bias, model drift and fairness across deployed models.
> `Explainable AI` · `Bias Detection` · `Data Ethics`

> **🎯 Reinforcement Learning for Autonomous Drone Navigation** — real-time path planning and obstacle avoidance in complex environments.
> `Reinforcement Learning` · `Simulation` · `Robotics` · `Gymnasium`

---

## 🧰 Tech Stack

| Area | Tools |
| :--- | :--- |
| **Languages** | `Python` `R` `SQL` `C` `COBOL` |
| **Data Science & ML** | `Pandas` `NumPy` `Scikit-learn` `PyTorch` `TensorFlow` `XGBoost` `LightGBM` `Optuna` `Hugging Face Transformers` `spaCy` |
| **Evolutionary & RL** | `Evolution strategies` `CMA-ES` `Genetic algorithms` `Genetic programming` `PPO` `Imitation learning` |
| **Vision & 3D** | `OpenCV` `MediaPipe` `moderngl` `pygame` `Grad-CAM` `Kinect (custom libusb driver)` |
| **Performance** | `numba` `multiprocessing` |
| **Geo** | `OpenStreetMap` `Esri tiles` `Nominatim` `KML / GeoJSON` |
| **DevOps & Deployment** | `Docker` `Docker Compose` `Git` `GitHub Actions` `FastAPI` `Flask` `CI/CD` |
| **IoT** | `MQTT` `Raspberry Pi` `ESP32` `Arduino` |
| **Visualization & BI** | `Matplotlib` `Seaborn` `Plotly` `Power BI` `Shiny (R)` `tkinter` |

---

## 🎓 About Me

I am a **Data Governance Engineer and dual master's candidate in Big Data and Data Science**, with prior degrees in **Financial Administration and Nursing**.
My interdisciplinary background allows me to integrate technical systems, applied research, and ethical innovation in domains such as health, security, and environmental resilience.

---

## 📫 Contact & Connect

<p align="left">
  <a href="https://www.linkedin.com/in/alromora"><img src="https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" /></a>
  <a href="https://github.com/xymora/repository"><img src="https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white" /></a>
  <a href="mailto:rodrigowifi@gmail.com"><img src="https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white" /></a>
</p>

---

<p align="center">
  <i>“Technology without purpose is noise. My goal is to engineer systems that think, protect, and evolve.”</i>
</p>
