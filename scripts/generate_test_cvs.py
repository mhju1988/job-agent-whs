"""Generate test CV PDFs covering diverse candidate profiles for test coverage."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT  # noqa: F401
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: F401
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

W, H = A4
MARGIN = 2 * cm
BASE = Path("E:/Studium/Agentic AI/test_data/cvs")

NAME = ParagraphStyle("name", fontSize=18, fontName="Helvetica-Bold", spaceAfter=2)
TITLE = ParagraphStyle(
    "title",
    fontSize=11,
    fontName="Helvetica",
    spaceAfter=6,
    textColor=colors.HexColor("#444444"),
)
H1 = ParagraphStyle(
    "h1",
    fontSize=11,
    fontName="Helvetica-Bold",
    spaceBefore=10,
    spaceAfter=4,
    textColor=colors.HexColor("#1a1a1a"),
)
BODY = ParagraphStyle(
    "body", fontSize=9, fontName="Helvetica", spaceAfter=3, leading=13
)
BULLET = ParagraphStyle(
    "bullet",
    fontSize=9,
    fontName="Helvetica",
    spaceAfter=2,
    leading=13,
    leftIndent=12,
)


def hr() -> HRFlowable:
    return HRFlowable(
        width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=4
    )


def section(text: str) -> list:
    return [Paragraph(text, H1), hr()]


def bullet(text: str) -> Paragraph:
    return Paragraph(f"• {text}", BULLET)


def para(text: str) -> Paragraph:
    return Paragraph(text, BODY)


def sp(n: int = 6) -> Spacer:
    return Spacer(1, n)


def build(filename: str, story: list) -> None:
    path = BASE / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )
    doc.build(story)
    print(f"Created {path}")


# ── 1. Career changer: lawyer → legal tech / product ──────────────────────────
build(
    "cv_career_changer_julia_weber.pdf",
    [
        Paragraph("Julia Weber", NAME),
        Paragraph("Career Changer — Legal Tech &amp; Product Management", TITLE),
        para(
            "Email: julia.weber@example.com  |  Phone: +49 176 5544 3322  "
            "|  Location: Hamburg, Germany"
        ),
        sp(),
        *section("Professional Summary"),
        para(
            "Former corporate lawyer with 6 years of litigation and contract experience, "
            "now pivoting to product management in the legal-tech and compliance-automation space. "
            "Completed a Product Management certification (PSPO I) in 2023. Strong analytical "
            "background, comfortable translating complex legal requirements into product "
            "requirements. No hands-on coding experience but familiar with Agile workflows "
            "and JIRA."
        ),
        sp(),
        *section("Skills"),
        para(
            "<b>Domain:</b> Contract law, GDPR compliance, regulatory analysis, legal research"
        ),
        para(
            "<b>Product:</b> User story mapping, backlog grooming, stakeholder interviews, "
            "roadmapping"
        ),
        para("<b>Tools:</b> JIRA, Confluence, Miro, Microsoft Office, Notion"),
        para(
            "<b>Methods:</b> Agile/Scrum (PSPO I certified), design thinking workshops"
        ),
        sp(),
        *section("Professional Experience"),
        para(
            "<b>Associate Attorney | Bremer &amp; Kollegen Rechtsanwaelte, Hamburg "
            "| 2017 - 2023</b>"
        ),
        bullet(
            "Advised mid-size companies on data protection (GDPR), contracts, and employment law."
        ),
        bullet(
            "Led a 12-month project to digitise client onboarding: reduced turnaround by 40%."
        ),
        bullet("Authored internal legal knowledge base used by 20+ attorneys."),
        para("<b>Legal Intern | Allianz SE, Munich | 2016</b>"),
        bullet("Supported the compliance team on MiFID II implementation project."),
        bullet(
            "Reviewed third-party vendor contracts and flagged data-sharing clauses."
        ),
        sp(),
        *section("Education"),
        para("<b>Product Management Certificate (PSPO I) | Scrum.org | 2023</b>"),
        para(
            "<b>First State Examination in Law (Erstes Staatsexamen) "
            "| University of Hamburg | 2016</b>"
        ),
        sp(),
        *section("Languages"),
        para("German (native), English (fluent, C1), French (intermediate, B1)"),
    ],
)

# ── 2. German-language Lebenslauf ─────────────────────────────────────────────
build(
    "cv_german_lebenslauf_hans_kaufmann.pdf",
    [
        Paragraph("Hans Kaufmann", NAME),
        Paragraph("Softwareentwickler (Java / Spring Boot)", TITLE),
        para(
            "E-Mail: hans.kaufmann@beispiel.de  |  Telefon: +49 89 1234 5678  "
            "|  Wohnort: Stuttgart"
        ),
        sp(),
        *section("Berufsprofil"),
        para(
            "Erfahrener Softwareentwickler mit 7 Jahren Berufserfahrung in der Entwicklung "
            "von Unternehmensanwendungen mit Java und Spring Boot. Schwerpunkte liegen in der "
            "Microservices-Architektur, REST-API-Entwicklung und der Integration von "
            "Messaging-Systemen (Apache Kafka). Ausgepragte Kenntnisse in agilen "
            "Entwicklungsmethoden (Scrum, Kanban) sowie im DevOps-Bereich."
        ),
        sp(),
        *section("Fachkenntnisse"),
        para(
            "<b>Programmiersprachen:</b> Java (Hauptsprache), Kotlin, Python (Grundkenntnisse), "
            "SQL"
        ),
        para(
            "<b>Frameworks:</b> Spring Boot, Spring Security, Hibernate/JPA, JUnit 5, Mockito"
        ),
        para(
            "<b>Infrastruktur:</b> Docker, Kubernetes, Jenkins CI/CD, GitLab, Apache Kafka"
        ),
        para("<b>Datenbanken:</b> PostgreSQL, MySQL, Oracle DB, Redis"),
        para("<b>Methoden:</b> Scrum, Kanban, TDD, Clean Code, DDD"),
        sp(),
        *section("Berufserfahrung"),
        para(
            "<b>Senior Softwareentwickler | Automobilzulieferer AG, Stuttgart | 2021 - heute</b>"
        ),
        bullet(
            "Entwurf und Implementierung eines Echtzeit-Fahrzeugtelemetrie-Systems "
            "(Java, Kafka, Kubernetes)."
        ),
        bullet(
            "Refaktorierung einer Legacy-Monolith-Anwendung in 8 Microservices; "
            "Deploymentzeit halbiert."
        ),
        bullet(
            "Technische Leitung eines 5-koepfigen Entwicklerteams; "
            "Einfuehrung von Code-Review-Standards."
        ),
        para(
            "<b>Softwareentwickler | FinanzSoft GmbH, Frankfurt | 2018 - 2021</b>"
        ),
        bullet(
            "Entwicklung von REST-APIs fuer ein Kernbankensystem auf Basis von "
            "Spring Boot und PostgreSQL."
        ),
        bullet(
            "Integration von Zahlungsdienstleistern (SEPA, PayPal) ueber "
            "standardisierte Schnittstellen."
        ),
        bullet(
            "Einfuehrung automatisierter Tests (JUnit, Mockito): "
            "Codeabdeckung von 35% auf 80% erhoet."
        ),
        para("<b>Junior-Entwickler | WebAgency Stuttgart UG | 2017 - 2018</b>"),
        bullet(
            "Pflege und Weiterentwicklung von Java-EE-Webanwendungen "
            "fuer Kunden aus dem Handelsbereich."
        ),
        sp(),
        *section("Ausbildung"),
        para(
            "<b>B.Sc. Wirtschaftsinformatik | Hochschule fuer Technik Stuttgart "
            "| 2014 - 2017</b>"
        ),
        para(
            "Bachelorarbeit: Leistungsoptimierung von Datenbankabfragen in ERP-Systemen"
        ),
        sp(),
        *section("Sprachen"),
        para("Deutsch (Muttersprache), Englisch (fliessend, C1), Franzoesisch (A2)"),
        sp(),
        *section("Zertifikate"),
        para("Oracle Certified Professional — Java SE 11 Developer (2022)"),
        para("AWS Certified Developer — Associate (2023)"),
    ],
)

# ── 3. Senior ML Engineer ─────────────────────────────────────────────────────
build(
    "cv_senior_ml_sarah_chen.pdf",
    [
        Paragraph("Sarah Chen", NAME),
        Paragraph("Senior Machine Learning Engineer", TITLE),
        para(
            "Email: sarah.chen@example.com  |  Phone: +49 30 9988 7766  "
            "|  Location: Berlin, Germany"
        ),
        para(
            "GitHub: github.com/schen-ml  |  LinkedIn: linkedin.com/in/sarah-chen-ml"
        ),
        sp(),
        *section("Professional Summary"),
        para(
            "Machine Learning Engineer with 9 years of experience taking models from research "
            "to production. Specialises in NLP, recommendation systems, and MLOps. "
            "Published 3 papers on efficient transformer architectures. Comfortable leading "
            "cross-functional teams bridging data science and software engineering."
        ),
        sp(),
        *section("Technical Skills"),
        para(
            "<b>ML / DL:</b> PyTorch, TensorFlow, Hugging Face Transformers, "
            "scikit-learn, XGBoost, LightGBM"
        ),
        para(
            "<b>MLOps:</b> MLflow, Kubeflow Pipelines, Weights &amp; Biases, "
            "Apache Airflow, DVC"
        ),
        para(
            "<b>Languages:</b> Python (expert), SQL, Bash, Scala (proficient)"
        ),
        para(
            "<b>Infrastructure:</b> Kubernetes, Docker, AWS SageMaker, GCP Vertex AI"
        ),
        para(
            "<b>Data:</b> Spark, Kafka, dbt, Snowflake, BigQuery, Feast (feature store)"
        ),
        sp(),
        *section("Professional Experience"),
        para("<b>Staff ML Engineer | Zalando SE, Berlin | 2021 - Present</b>"),
        bullet(
            "Built personalised fashion recommendation engine serving 50M users; +12% CTR."
        ),
        bullet(
            "Designed and owned the ML platform (Kubeflow + MLflow) used by 40 engineers."
        ),
        bullet(
            "Led NLP project: fine-tuned multilingual BERT to extract product attributes; "
            "reduced manual tagging by 70%."
        ),
        para(
            "<b>Senior ML Engineer | HERE Technologies, Berlin | 2018 - 2021</b>"
        ),
        bullet(
            "Developed map-matching and ETA prediction models deployed in production "
            "on Spark + SageMaker."
        ),
        bullet(
            "Reduced model training time by 60% through distributed GPU training strategies."
        ),
        para("<b>Data Scientist | ImmobilienScout24, Berlin | 2015 - 2018</b>"),
        bullet(
            "Built real-estate price prediction model (gradient boosting, 92% accuracy)."
        ),
        bullet("Introduced A/B testing framework used across 6 product teams."),
        sp(),
        *section("Education"),
        para(
            "<b>M.Sc. Computer Science (Machine Learning focus) | TU Berlin | 2013 - 2015</b>"
        ),
        para(
            "Thesis: Attention Mechanisms for Sequential Recommendation "
            "-- Best Thesis Award"
        ),
        para("<b>B.Sc. Mathematics | Peking University | 2009 - 2013</b>"),
        sp(),
        *section("Languages"),
        para("Mandarin (native), English (fluent, C2), German (professional, B2)"),
    ],
)

# ── 4. UX / Product Designer ──────────────────────────────────────────────────
build(
    "cv_ux_designer_yara_hassan.pdf",
    [
        Paragraph("Yara Hassan", NAME),
        Paragraph("Senior UX / Product Designer", TITLE),
        para(
            "Email: yara.hassan@example.com  |  Phone: +49 221 4433 2211  "
            "|  Location: Cologne, Germany"
        ),
        para(
            "Portfolio: yarahassan.design  |  LinkedIn: linkedin.com/in/yara-hassan-ux"
        ),
        sp(),
        *section("Professional Summary"),
        para(
            "User-centred designer with 7 years of experience creating intuitive digital "
            "products for B2C and B2B audiences. Expert in end-to-end UX: from discovery "
            "and research through prototyping to design system ownership. "
            "No programming background; collaborates closely with engineering and product."
        ),
        sp(),
        *section("Skills"),
        para(
            "<b>Design tools:</b> Figma, Sketch, Adobe XD, Principle, ProtoPie"
        ),
        para(
            "<b>Research:</b> User interviews, usability testing, contextual inquiry, "
            "card sorting, tree testing, survey design (Typeform, Maze)"
        ),
        para(
            "<b>Methods:</b> Design thinking, Jobs-to-be-Done, double diamond, Lean UX"
        ),
        para(
            "<b>Collaboration:</b> Zeplin, Storybook (handoff), Miro, Notion, JIRA, Confluence"
        ),
        para(
            "<b>Analytics:</b> Hotjar, FullStory, Mixpanel, Google Analytics (read-level)"
        ),
        sp(),
        *section("Professional Experience"),
        para(
            "<b>Lead UX Designer | HealthTech Startup (Series B), Cologne | 2021 - Present</b>"
        ),
        bullet(
            "Owned product design for patient-facing mobile app (iOS/Android); "
            "grew DAU from 8K to 120K over 2 years."
        ),
        bullet(
            "Ran 30+ moderated usability sessions; redesigned onboarding flow, "
            "reducing drop-off by 45%."
        ),
        bullet(
            "Built and maintained company-wide design system (150+ components in Figma)."
        ),
        para("<b>UX Designer | Otto GmbH, Hamburg | 2018 - 2021</b>"),
        bullet(
            "Redesigned checkout flow for e-commerce platform; +8% conversion rate."
        ),
        bullet(
            "Established UX research practice: first dedicated research function "
            "in the department."
        ),
        para("<b>Junior UX Designer | Digital Agency, Cologne | 2017 - 2018</b>"),
        bullet("Delivered wireframes and prototypes for 10+ client websites."),
        sp(),
        *section("Education"),
        para(
            "<b>B.A. Communication Design | Hochschule fuer Medien, Stuttgart | 2013 - 2017</b>"
        ),
        para(
            "Thesis: Accessibility in Mobile UX -- Designing for Cognitive Impairment"
        ),
        sp(),
        *section("Languages"),
        para("Arabic (native), German (fluent, C1), English (fluent, C1)"),
    ],
)

# ── 5. Sparse / minimal CV ────────────────────────────────────────────────────
build(
    "cv_sparse_minimal_oliver_braun.pdf",
    [
        Paragraph("Oliver Braun", NAME),
        Paragraph("Software Developer", TITLE),
        para("Email: o.braun@mail.de  |  Location: Leipzig"),
        sp(),
        *section("About"),
        para(
            "I am a software developer with some experience in web development. "
            "Looking for a new position."
        ),
        sp(),
        *section("Experience"),
        para("<b>Developer | Small Web Agency, Leipzig | 2022 - 2024</b>"),
        bullet("Worked on various client websites using WordPress and PHP."),
        bullet("Some experience with JavaScript and CSS."),
        sp(),
        *section("Education"),
        para(
            "<b>Ausbildung Fachinformatiker Anwendungsentwicklung | 2019 - 2022</b>"
        ),
        sp(),
        *section("Skills"),
        para("PHP, WordPress, JavaScript, HTML, CSS, MySQL"),
        sp(),
        *section("Languages"),
        para("German (native), English (basic)"),
    ],
)

print("\nAll 5 test CVs created successfully.")
