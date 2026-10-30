from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from SPARQLWrapper import JSON, SPARQLWrapper


# -----------------------------------------------------------------------------
# Basic application settings
# -----------------------------------------------------------------------------
APP_TITLE = "CelloGraph"

# GraphDB connection settings are embedded in the code.
# Change these values here if the server, repository, or credentials change.
GRAPHDB_ENDPOINT = "http://18.219.172.51:7200/repositories/cellograph"
GRAPHDB_USERNAME = ""
GRAPHDB_PASSWORD = ""

ASSETS_DIR = Path(__file__).parent / "assets"


# -----------------------------------------------------------------------------
# Predefined competency questions (CQs)
# -----------------------------------------------------------------------------
# Every query is self-contained. No publication ID or other separate input is
# required. Selecting a CQ in the sidebar automatically runs its SPARQL query.
CQ_DEFINITIONS: dict[str, dict[str, str]] = {
    "Co-occurance of Terms in Paragraph": {
        "question": (
            "Which two terms occur in the same paragraph? "
            "In which publications and paragraphs do they occur?"
        ),
        "description": "",
        "query": """
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX onner: <http://purl.org/spatialai/onner/onner-full#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?publication ?doi ?paraId ?paragraph ?term1 ?label1 ?term2 ?label2 WHERE {
    ?pubId rdf:type onner:ScholarlyPublication ;
        onner:publicationTitle ?publication ;
        onner:doi ?doi ;
        onner:containsDocumentPart ?paraId .

    ?paraId rdf:type onner:Paragraph ;
        onner:paragraphText ?paragraph ;
        onner:directlyContainsLabeledTerm ?termId1 ;
        onner:directlyContainsLabeledTerm ?termId2 .

    FILTER(?termId1 != ?termId2)

    ?termId1 onner:labeledTermText ?term1 ;
        onner:hasLabeledTermStatus ?status1 .
    ?status1 rdf:type ?statusType1 ;
        onner:statusAssignmentDate ?statusDate1 ;
        onner:hasLabeledTermLabel ?labelId1 .
    ?labelId1 onner:labelText ?label1 .

    FILTER(?statusType1 IN (onner:AcceptedStatus, onner:SuggestedStatus))
    FILTER NOT EXISTS {
        ?termId1 onner:hasLabeledTermStatus ?newStatus1 .
        ?newStatus1 onner:statusAssignmentDate ?newStatusDate1 .
        FILTER(?newStatusDate1 > ?statusDate1)
    }

    ?termId2 onner:labeledTermText ?term2 ;
        onner:hasLabeledTermStatus ?status2 .
    ?status2 rdf:type ?statusType2 ;
        onner:statusAssignmentDate ?statusDate2 ;
        onner:hasLabeledTermLabel ?labelId2 .
    ?labelId2 onner:labelText ?label2 .

    FILTER(?statusType2 IN (onner:AcceptedStatus, onner:SuggestedStatus))
    FILTER NOT EXISTS {
        ?termId2 onner:hasLabeledTermStatus ?newStatus2 .
        ?newStatus2 onner:statusAssignmentDate ?newStatusDate2 .
        FILTER(?newStatusDate2 > ?statusDate2)
    }
}
""".strip(),
    },
    "Publications by Term Frequency": {
        "question": (
            "What are the most recent publications that mention a specified "
            "term at least a specified number of times?"
        ),
        "description": "",
        "query": """
PREFIX onner: <http://purl.org/spatialai/onner/onner-full#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?publication ?date ?doi
WHERE {
    ?publicationId rdf:type onner:ScholarlyPublication ;
        onner:publicationTitle ?publication ;
        onner:publicationDate ?date ;
        onner:doi ?doi ;
        onner:containsDocumentPart ?paragraphId .

    ?paragraphId rdf:type onner:Paragraph ;
        onner:directlyContainsLabeledTerm ?termId .

    ?termId rdf:type onner:LabeledTerm ;
        onner:labeledTermText ?term ;
        onner:hasLabeledTermStatus ?status .

    ?status rdf:type ?statusType ;
        onner:statusAssignmentDate ?statusDate .

    FILTER(LCASE(STR(?term)) = LCASE("__CQ2_TERM__"))
    FILTER(?statusType IN (onner:AcceptedStatus, onner:SuggestedStatus))

    FILTER NOT EXISTS {
        ?termId onner:hasLabeledTermStatus ?newStatus .
        ?newStatus onner:statusAssignmentDate ?newStatusDate .
        FILTER(?newStatusDate > ?statusDate)
    }
}
GROUP BY ?publication ?date ?doi
HAVING (COUNT(?term) >= __CQ2_COUNT__)
ORDER BY DESC(?date)
""".strip(),
    },

    "Terms by Label and Publication": {
        "question": (
            "Find all terms with a specified label from a particular publication."
        ),
        "description": "",
        "query": """
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX onner: <http://purl.org/spatialai/onner/onner-full#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?publication ?doi ?paraId ?paragraph ?term ?label
WHERE {
    ?pubId rdf:type onner:ScholarlyPublication ;
        onner:publicationTitle ?publication ;
        onner:doi ?doi ;
        onner:containsDocumentPart ?paraId .

    ?paraId rdf:type onner:Paragraph ;
        onner:paragraphText ?paragraph ;
        onner:directlyContainsLabeledTerm ?termId .

    ?termId onner:labeledTermText ?term ;
        onner:hasLabeledTermStatus ?status .

    ?status rdf:type ?statusType ;
        onner:statusAssignmentDate ?statusDate ;
        onner:hasLabeledTermLabel ?labelId .
    ?labelId onner:labelText ?label .

    FILTER(
        LCASE(STR(?publication)) = LCASE("__CQ3_PUBLICATION__")
        || LCASE(STR(?doi)) = LCASE("__CQ3_PUBLICATION__")
    )
    FILTER(UCASE(STR(?label)) = UCASE("__CQ3_LABEL__"))
    FILTER(?statusType IN (onner:AcceptedStatus, onner:SuggestedStatus))

    FILTER NOT EXISTS {
        ?termId onner:hasLabeledTermStatus ?newStatus .
        ?newStatus onner:statusAssignmentDate ?newStatusDate .
        FILTER(?newStatusDate > ?statusDate)
    }
}
""".strip(),
    },

}


# Questions and SPARQL queries from queries(1).txt (unaltered query bodies).
CQ_DEFINITIONS.update({
    'Annotation CQ 1': {
        "question": 'Which publications are represented in the system?',
        "description": "",
        "query": 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX onner: <http://purl.org/spatialai/onner/onner-full#>\n\nSELECT * WHERE {\n    ?pubId rdf:type onner:ScholarlyPublication ;\n           onner:publicationTitle ?title ;\n           onner:doi ?doi .\n\n    OPTIONAL {\n        ?pubId onner:publicationDate ?pubDate .\n    }\n}\nORDER BY DESC(?pubDate)',
    },
    'Annotation CQ 2': {
        "question": 'How many entities does each publication contain, considering only entities whose latest status is either Accepted or Suggested?',
        "description": "",
        "query": 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX onner: <http://purl.org/spatialai/onner/onner-full#>\n\nSELECT ?pubId ?title ?pubDate ?doi (COUNT(?entId) AS ?entCount)\nWHERE {\n    ?pubId rdf:type onner:ScholarlyPublication ;\n           onner:publicationTitle ?title ;\n           onner:doi ?doi .\n\n    OPTIONAL {\n        ?pubId onner:publicationDate ?pubDate .\n    }\n\n    ?pubId onner:containsDocumentPart ?entId .\n    ?entId rdf:type onner:LabeledTerm ;\n           onner:hasLabeledTermStatus ?status .\n\n    ?status rdf:type ?statusType ;\n            onner:statusAssignmentDate ?statusDate .\n\n    # Latest status must be Accepted or Suggested.\n    FILTER(\n        ?statusType IN (\n            onner:AcceptedStatus,\n            onner:SuggestedStatus\n        )\n    )\n\n    # No status with a later assignment date can exist.\n    FILTER NOT EXISTS {\n        ?entId onner:hasLabeledTermStatus ?newStatus .\n        ?newStatus onner:statusAssignmentDate ?newStatusDate .\n        FILTER(?newStatusDate > ?statusDate)\n    }\n}\nGROUP BY ?pubId ?title ?pubDate ?doi\nORDER BY DESC(?pubDate)',
    },
    'Annotation CQ 3': {
        "question": 'How many unique entity-label pairs does each publication contain, considering only entities whose latest status is either Accepted or Suggested?',
        "description": "",
        "query": 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX onner: <http://purl.org/spatialai/onner/onner-full#>\n\nSELECT ?pubId ?title ?pubDate ?doi (COUNT(*) AS ?uniquePair) WHERE {\n    SELECT DISTINCT ?pubId ?title ?pubDate ?doi ?ent ?label WHERE {\n        ?pubId rdf:type onner:ScholarlyPublication ;\n            onner:publicationTitle ?title ;\n            onner:doi ?doi .\n\n        OPTIONAL {\n            ?pubId onner:publicationDate ?pubDate .\n        }\n\n        ?pubId onner:containsDocumentPart ?entId .\n        ?entId rdf:type onner:LabeledTerm ;\n            onner:labeledTermText ?ent ;\n            onner:hasLabeledTermStatus ?status .\n\n        ?status rdf:type ?statusType ;\n            onner:statusAssignmentDate ?statusDate ;\n            onner:hasLabeledTermLabel ?labelId .\n\n        ?labelId onner:labelText ?label .\n\n        # Latest status must be Accepted or Suggested.\n        FILTER(\n            ?statusType IN (\n                onner:AcceptedStatus,\n                onner:SuggestedStatus\n            )\n        )\n\n        # No status with a later assignment date can exist.\n        FILTER NOT EXISTS {\n            ?entId onner:hasLabeledTermStatus ?newStatus .\n            ?newStatus onner:statusAssignmentDate ?newStatusDate .\n            FILTER(?newStatusDate > ?statusDate)\n        }\n    }\n}\nGROUP BY ?pubId ?title ?pubDate ?doi\nORDER BY DESC(?pubDate)',
    },
    'Annotation CQ 4': {
        "question": 'How many entities are associated with each label, considering only entities whose latest status is either Accepted or Suggested?',
        "description": "",
        "query": 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX onner: <http://purl.org/spatialai/onner/onner-full#>\n\nSELECT ?label (COUNT(DISTINCT ?entId) AS ?entCount) WHERE {\n    ?entId rdf:type onner:LabeledTerm ;\n    \tonner:hasLabeledTermStatus ?status .\n    \n    ?status rdf:type ?statusType ;\n    \tonner:statusAssignmentDate ?statusDate ;\n        onner:hasLabeledTermLabel ?labelId .\n    \n    ?labelId onner:labelText ?label .\n    \n    # latest status must be Accepted or Suggested\n    FILTER(\n        ?statusType IN (\n        \tonner:AcceptedStatus,\n            onner:SuggestedStatus\n        )\n    )\n    \n    # no status with a later assignment date can exist\n    FILTER NOT EXISTS {\n        ?entId onner:hasLabeledTermStatus ?newStatus .\n        ?newStatus onner:statusAssignmentDate ?newStatusDate .\n        FILTER(?newStatusDate > ?statusDate)\n    }\n}\nGROUP BY ?label\nORDER BY DESC(?label)',
    },
    'Annotation CQ 5': {
        "question": 'How many unique entities are associated with each label, considering only entities whose latest status is either Accepted or Suggested?',
        "description": "",
        "query": 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX onner: <http://purl.org/spatialai/onner/onner-full#>\n\nSELECT ?label (COUNT(DISTINCT ?ent) AS ?entCount) WHERE {\n    ?entId rdf:type onner:LabeledTerm ;\n    \tonner:labeledTermText ?ent ;\n    \tonner:hasLabeledTermStatus ?status .\n    \n    ?status rdf:type ?statusType ;\n    \tonner:statusAssignmentDate ?statusDate ;\n        onner:hasLabeledTermLabel ?labelId .\n    \n    ?labelId onner:labelText ?label .\n    \n    # latest status must be Accepted or Suggested\n    FILTER(\n        ?statusType IN (\n        \tonner:AcceptedStatus,\n            onner:SuggestedStatus\n        )\n    )\n    \n    # no status with a later assignment date can exist\n    FILTER NOT EXISTS {\n        ?entId onner:hasLabeledTermStatus ?newStatus .\n        ?newStatus onner:statusAssignmentDate ?newStatusDate .\n        FILTER(?newStatusDate > ?statusDate)\n    }\n}\nGROUP BY ?label\nORDER BY DESC(?label)',
    },
    'Annotation CQ 6': {
        "question": 'Which labeled terms have been assigned different labels across multiple occurrences, considering only those whose latest status is Accepted or Suggested, and what are their entity IDs, latest status IDs, and corresponding labels?',
        "description": "",
        "query": 'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\nPREFIX onner: <http://purl.org/spatialai/onner/onner-full#>\n\nSELECT ?ent ?entityId ?statusId ?label\nWHERE {\n    ?entId rdf:type onner:LabeledTerm ;\n           onner:labeledTermText ?ent ;\n           onner:hasLabeledTermStatus ?status .\n\n    ?status rdf:type ?statusType ;\n            onner:statusAssignmentDate ?statusDate ;\n            onner:hasLabeledTermLabel ?labelId .\n\n    ?labelId onner:labelText ?label .\n\n    # Consider only entities whose latest status is Accepted or Suggested.\n    FILTER(\n        ?statusType IN (\n            onner:AcceptedStatus,\n            onner:SuggestedStatus\n        )\n    )\n\n    # No status with a later assignment date can exist.\n    FILTER NOT EXISTS {\n        ?entId onner:hasLabeledTermStatus ?newStatus .\n        ?newStatus onner:statusAssignmentDate ?newDate .\n        FILTER(?newDate > ?statusDate)\n    }\n\n    # Find entity texts assigned different labels.\n    FILTER EXISTS {\n        ?otherEntId rdf:type onner:LabeledTerm ;\n                    onner:labeledTermText ?ent ;\n                    onner:hasLabeledTermStatus ?otherStatus .\n\n        ?otherStatus rdf:type ?otherStatusType ;\n                     onner:statusAssignmentDate ?otherDate ;\n                     onner:hasLabeledTermLabel ?otherLabelId .\n\n        ?otherLabelId onner:labelText ?otherLabel .\n\n        FILTER(?otherLabel != ?label)\n\n        FILTER(\n            ?otherStatusType IN (\n                onner:AcceptedStatus,\n                onner:SuggestedStatus\n            )\n        )\n\n        FILTER NOT EXISTS {\n            ?otherEntId onner:hasLabeledTermStatus ?newOtherStatus .\n            ?newOtherStatus onner:statusAssignmentDate ?newOtherDate .\n            FILTER(?newOtherDate > ?otherDate)\n        }\n    }\n\n    # Extract IDs without their full IRIs.\n    BIND(REPLACE(STR(?entId), "^.*[/#]", "") AS ?entityId)\n    BIND(REPLACE(STR(?status), "^.*[/#]", "") AS ?statusId)\n}\nORDER BY ?ent ?label ?entityId',
    },
})

# Sidebar categories. The existing three CQs remain unchanged.
CQ_CATEGORIES = {
    "Knowledge Discovery": [
        "Co-occurance of Terms in Paragraph",
        "Publications by Term Frequency",
        "Terms by Label and Publication",
    ],
    "Annotation Analysis": [
        "Annotation CQ 1", "Annotation CQ 2", "Annotation CQ 3",
        "Annotation CQ 4", "Annotation CQ 5", "Annotation CQ 6",
    ],
}



# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------
def queue_selected_category() -> None:
    """Choose the first CQ in the newly selected category."""
    st.session_state.selected_cq = CQ_CATEGORIES[st.session_state.selected_category][0]
    queue_selected_query()


def queue_selected_query() -> None:
    """Update the selected FAQ without executing its query."""
    selected_name = st.session_state.selected_cq

    st.session_state.active_question = CQ_DEFINITIONS[selected_name]["question"]
    st.session_state.custom_question_error = ""
    st.session_state.run_selected_query = False
    st.session_state.result_json = None
    st.session_state.result_df = None
    st.session_state.error_message = ""


def escape_sparql_literal(value: str) -> str:
    """Escape a text value before inserting it into a SPARQL string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"').strip()


def build_cq1_query() -> str:
    """Build CQ1 and add filters only for values entered by the user."""
    term_1 = escape_sparql_literal(st.session_state.cq1_term_1)
    label_1 = escape_sparql_literal(st.session_state.cq1_label_1)
    term_2 = escape_sparql_literal(st.session_state.cq1_term_2)
    label_2 = escape_sparql_literal(st.session_state.cq1_label_2)

    filters = []

    if term_1:
        filters.append(
            f'    FILTER(LCASE(STR(?term1)) = LCASE("{term_1}"))'
        )

    if label_1:
        filters.append(
            f'    FILTER(UCASE(STR(?label1)) = UCASE("{label_1}"))'
        )

    if term_2:
        filters.append(
            f'    FILTER(LCASE(STR(?term2)) = LCASE("{term_2}"))'
        )

    if label_2:
        filters.append(
            f'    FILTER(UCASE(STR(?label2)) = UCASE("{label_2}"))'
        )

    base_query = CQ_DEFINITIONS[
        "Co-occurance of Terms in Paragraph"
    ]["query"]

    if not filters:
        return base_query

    closing_brace_index = base_query.rfind("}")
    return (
        base_query[:closing_brace_index].rstrip()
        + "\n\n"
        + "\n".join(filters)
        + "\n}"
    )



def queue_cq1_query() -> None:
    """Run CQ1 with any provided filters, or run the full query if none exist."""
    st.session_state.pending_query = build_cq1_query()
    st.session_state.active_question = CQ_DEFINITIONS[
        "Co-occurance of Terms in Paragraph"
    ]["question"]
    st.session_state.custom_question_error = ""
    st.session_state.run_selected_query = True
    st.session_state.result_json = None
    st.session_state.result_df = None
    st.session_state.error_message = ""



def build_cq2_query() -> str:
    """Build CQ2 using the term and minimum occurrence count entered by the user."""
    term = escape_sparql_literal(st.session_state.cq2_term)
    occurrence_count = int(st.session_state.cq2_occurrence_count)

    return (
        CQ_DEFINITIONS["Publications by Term Frequency"]["query"]
        .replace("__CQ2_TERM__", term)
        .replace("__CQ2_COUNT__", str(occurrence_count))
    )


def queue_cq2_query() -> None:
    """Run CQ2 using the user-provided term and minimum occurrence count."""
    st.session_state.pending_query = build_cq2_query()
    st.session_state.active_question = CQ_DEFINITIONS[
        "Publications by Term Frequency"
    ]["question"]
    st.session_state.custom_question_error = ""
    st.session_state.run_selected_query = True
    st.session_state.result_json = None
    st.session_state.result_df = None
    st.session_state.error_message = ""


def build_cq3_query() -> str:
    """Build CQ3 using the publication title or DOI and label entered by the user."""
    publication = escape_sparql_literal(st.session_state.cq3_publication)
    label = escape_sparql_literal(st.session_state.cq3_label)

    return (
        CQ_DEFINITIONS["Terms by Label and Publication"]["query"]
        .replace("__CQ3_PUBLICATION__", publication)
        .replace("__CQ3_LABEL__", label)
    )


def queue_cq3_query() -> None:
    """Run CQ3 using the user-provided publication title or DOI and label."""
    st.session_state.pending_query = build_cq3_query()
    st.session_state.active_question = CQ_DEFINITIONS[
        "Terms by Label and Publication"
    ]["question"]
    st.session_state.custom_question_error = ""
    st.session_state.run_selected_query = True
    st.session_state.result_json = None
    st.session_state.result_df = None
    st.session_state.error_message = ""


def queue_current_query() -> None:
    """Run the currently selected CQ when the Execute button is clicked."""
    selected_name = st.session_state.selected_cq

    if selected_name == "Co-occurance of Terms in Paragraph":
        queue_cq1_query()
        return

    if selected_name == "Publications by Term Frequency":
        queue_cq2_query()
        return

    if selected_name == "Terms by Label and Publication":
        queue_cq3_query()
        return

    st.session_state.pending_query = CQ_DEFINITIONS[selected_name]["query"]
    st.session_state.active_question = CQ_DEFINITIONS[selected_name]["question"]
    st.session_state.custom_question_error = ""
    st.session_state.run_selected_query = True
    st.session_state.result_json = None
    st.session_state.result_df = None
    st.session_state.error_message = ""


def normalize_question(question: str) -> str:
    """Normalize a natural-language question for simple matching."""
    return " ".join(question.lower().strip().rstrip("?.!").split())


def queue_custom_question() -> None:
    """Translate one supported custom question into a SPARQL query."""
    question = st.session_state.custom_question.strip()
    normalized_question = normalize_question(question)

    # This first version supports one working custom question and a few
    # natural variations of the same question. More mappings can be added later.
    supported_questions = {
        normalize_question(CQ_DEFINITIONS[cq_name]["question"]): cq_name
        for cq_name in CQ_DEFINITIONS
    }

    matched_cq = supported_questions.get(normalized_question)

    if not matched_cq:
        st.session_state.run_selected_query = False
        st.session_state.custom_question_error = (
            "This demo currently supports the predefined demo questions."
        )
        return

    st.session_state.pending_query = CQ_DEFINITIONS[matched_cq]["query"]
    st.session_state.active_question = question
    st.session_state.custom_question_error = ""
    st.session_state.run_selected_query = True
    st.session_state.result_json = None
    st.session_state.result_df = None
    st.session_state.error_message = ""


def run_sparql_query(query: str) -> dict[str, Any]:
    """Send a SELECT or ASK query to the embedded GraphDB endpoint."""
    sparql = SPARQLWrapper(GRAPHDB_ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(30)

    # Credentials are optional. Leave both values empty for an open endpoint.
    if GRAPHDB_USERNAME.strip():
        sparql.setCredentials(GRAPHDB_USERNAME, GRAPHDB_PASSWORD)

    return sparql.query().convert()


def sparql_json_to_dataframe(data: dict[str, Any]) -> pd.DataFrame:
    """Convert a SPARQL JSON response into a pandas DataFrame."""
    # ASK queries return one boolean value instead of result bindings.
    if "boolean" in data:
        return pd.DataFrame([{"result": data["boolean"]}])

    variables = data.get("head", {}).get("vars", [])
    bindings = data.get("results", {}).get("bindings", [])

    rows: list[dict[str, Any]] = []
    for binding in bindings:
        row: dict[str, Any] = {}
        for variable in variables:
            cell = binding.get(variable, {})
            row[variable] = cell.get("value", "")
        rows.append(row)

    return pd.DataFrame(rows, columns=variables)


def compact_uri(value: Any) -> str:
    """Create a short label from a full URI."""
    text = str(value)
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    if "/" in text:
        return text.rstrip("/").rsplit("/", 1)[-1]
    return text


def escape_dot_label(value: Any) -> str:
    """Escape text before placing it inside a Graphviz DOT string."""
    return compact_uri(value).replace("\\", "\\\\").replace('"', '\\"')


def dataframe_to_dot(dataframe: pd.DataFrame, row_limit: int = 80) -> str | None:
    """Build a directed graph when the result has at least two ID columns."""
    id_columns = [
        column for column in dataframe.columns if column.lower().endswith("id")
    ]

    if len(id_columns) < 2 or dataframe.empty:
        return None

    source_column, target_column = id_columns[:2]
    lines = [
        "digraph CelloGraph {",
        'rankdir="LR";',
        'graph [bgcolor="transparent", pad="0.2", nodesep="0.35", ranksep="0.55"];',
        'node [shape="box", style="rounded,filled", fillcolor="white", fontname="Arial"];',
        'edge [fontname="Arial"];',
    ]

    for _, row in dataframe.head(row_limit).iterrows():
        source = escape_dot_label(row[source_column])
        target = escape_dot_label(row[target_column])
        lines.append(f'"{source}" -> "{target}";')

    lines.append("}")
    return "\n".join(lines)


def render_paragraph_cards(dataframe: pd.DataFrame) -> None:
    """Show all unique paragraph results in a readable card layout."""
    if "paragraph" not in dataframe.columns:
        st.info("This result does not contain a paragraph column.")
        return

    if dataframe.empty:
        st.info("No paragraphs were returned.")
        return

    if "paraId" in dataframe.columns:
        unique_paragraphs = dataframe.drop_duplicates(subset=["paraId"])
    else:
        unique_paragraphs = dataframe.drop_duplicates(subset=["paragraph"])

    for index, row in unique_paragraphs.iterrows():
        paragraph_id = compact_uri(row.get("paraId", f"Paragraph {index + 1}"))
        paragraph_text = html.escape(str(row.get("paragraph", "")))

        st.markdown(
            f"""
            <div class="paragraph-card">
                <div class="paragraph-id">{html.escape(paragraph_id)}</div>
                <div class="paragraph-text">{paragraph_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# -----------------------------------------------------------------------------
# Page configuration and visual styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        @import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600;700&display=swap");
        
        .block-container {
            max-width: 1500px;
            padding-top: 4.5rem;
            padding-bottom: 2rem;
        }
        
        /*
        .app-title {
            text-align: center;
            font-size: 2.25rem;
            font-weight: 700;
            line-height: 1.25;
            margin: 0 0 0.2rem 0;
            overflow: visible;
            font-family: "IBM Plex Mono", monospace;
        }
        */
        
        .app-title {
            text-align: center;
            font-family: "IBM Plex Mono", monospace;
            font-size: 2.25rem;
            font-weight: 700;
            line-height: 1;
            letter-spacing: -0.04em;
            margin: 0 0 0.3rem 0;
            overflow: visible;
        }

        .app-subtitle {
            text-align: center;
            color: #667085;
            font-size: 1.4rem;
            margin-bottom: 1.2rem;
        }

        .section-label {
            font-size: 1.15rem;
            font-weight: 650;
            margin-bottom: 0.45rem;
        }

        .output-empty {
            min-height: 420px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            color: #667085;
            border: 1px dashed #c8cdd5;
            border-radius: 0.75rem;
            padding: 2rem;
        }

        .paragraph-card {
            border: 1px solid #e3e7ed;
            border-radius: 0.75rem;
            padding: 0.85rem 1rem;
            margin-bottom: 0.75rem;
            background: rgba(255, 255, 255, 0.03);
        }

        .paragraph-id {
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        .paragraph-text {
            line-height: 1.55;
        }

        .acknowledgement-box {
            max-width: 1100px;
            margin: 2rem auto 0 auto;
            /*padding: 1.15rem 1.35rem;*/
            padding: 0.35rem 1.35rem;
            border-left: 4px solid #667085;
            border-radius: 0.6rem;
            background: rgba(102, 112, 133, 0.08);
        }

        .acknowledgement-title {
            font-family: Georgia, "Times New Roman", serif;
            /*font-size: 1.05rem;*/
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            /*text-transform: uppercase;*/
            /*margin-bottom: 0.45rem;*/
        }

        .acknowledgement-text {
            font-family: Georgia, "Times New Roman", serif;
            /*font-size: 0.95rem;*/
            font-size: 0.85rem;
            line-height: 1.6;
            color: #667085;
        }

        section[data-testid="stSidebar"] pre {
            font-size: 0.76rem;
            line-height: 1.35;
        }
        
        section[data-testid="stSidebar"] hr {
            margin-top: 0.25rem !important;
            margin-bottom: 0.25rem !important;
        }

        .selected-question {
            white-space: normal;
            overflow-wrap: anywhere;
            line-height: 1.45;
            padding: 0.75rem 0.85rem;
            /*margin-top: 0.4rem;*/
            border: 1px solid #d9dee7;
            border-radius: 0.6rem;
            background: white;
        }
        
        /* div[data-testid="stMetricValue"] {
            font-size: 1.4rem;
            line-height: 1.2;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.85rem;
        } */

        /* CelloGraph teal palette — colors only, no layout changes. */
        :root { --cg-accent: #176a70; --cg-ink: #193743; --cg-line: #dce6e8; }
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #eff8f7 0px, #ffffff 350px);
            color: var(--cg-ink);
        }
        [data-testid="stSidebar"] {
            background-color: #f5f9f9;
            border-right-color: var(--cg-line);
        }
        [data-testid="stSidebar"] h2, .app-title, .section-label,
        .paragraph-id, .acknowledgement-title { color: var(--cg-ink); }
        .app-title { color: #176A70; }
        .app-subtitle, .acknowledgement-text, .output-empty { color: #627685; }
        .selected-question { border-color: var(--cg-line); border-left: 4px solid var(--cg-accent); background: #ffffff; color: #263c48; }
        .paragraph-card { border-color: var(--cg-line); background: #ffffff; }
        .paragraph-id { color: var(--cg-accent); }
        .paragraph-text { color: #263b46; }
        .output-empty { border-color: #afc9c9; background: #f5fbfa; }
        .selected-question-label { font-size:.64rem; font-weight:800; letter-spacing:.12em; color:#12676a; margin-bottom:7px; }
        /* Same Selected Question card appearance, with a native dropdown inside. */
        [data-testid="stSidebar"] .st-key-selected_question_box {
            white-space: normal;
            overflow-wrap: anywhere;
            line-height: 1.45;
            padding: 0.75rem 0.85rem;
            border: 1px solid var(--cg-line);
            border-left: 4px solid var(--cg-accent);
            border-radius: 0.6rem;
            background: #ffffff;
            color: #263c48;
        }
        [data-testid="stSidebar"] .st-key-selected_question_box [data-testid="stSelectbox"] > div > div {
            border: 0;
            background: transparent;
            box-shadow: none;
        }
        [data-testid="stSidebar"] .st-key-selected_question_box [data-testid="stSelectbox"] {
            margin: 0;
        }

        .acknowledgement-box { border-left-color: var(--cg-accent); background: #f7faf9; }
        [data-testid="stSidebarUserContent"] {
            padding-bottom: 2rem;
        }
        [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
            min-height: calc(100dvh - 7rem);
        }
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.acknowledgement-box) {
            margin-top: auto;
        }
        [data-testid="stMetric"] { background-color: #ffffff; border-color: var(--cg-line); }
        [data-testid="stMetricValue"] { color: var(--cg-accent); }
        [data-testid="stSidebar"] .stButton button[kind="primary"] {
            background-color: var(--cg-accent); border-color: var(--cg-accent); color: #ffffff;
        }
        [data-testid="stSidebar"] .stButton button[kind="primary"]:hover {
            background-color: #10575d; border-color: #10575d;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] { color: var(--cg-accent); }
        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--cg-accent); }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Session state initialization
# -----------------------------------------------------------------------------
first_cq_name = next(iter(CQ_DEFINITIONS))

if "selected_category" not in st.session_state:
    st.session_state.selected_category = "Knowledge Discovery"

if "selected_cq" not in st.session_state:
    st.session_state.selected_cq = first_cq_name

if "run_selected_query" not in st.session_state:
    # Wait for the user to click Execute.
    st.session_state.run_selected_query = False

if "cq1_term_1" not in st.session_state:
    st.session_state.cq1_term_1 = ""

if "cq1_label_1" not in st.session_state:
    st.session_state.cq1_label_1 = ""

if "cq1_term_2" not in st.session_state:
    st.session_state.cq1_term_2 = ""

if "cq1_label_2" not in st.session_state:
    st.session_state.cq1_label_2 = ""

if "cq2_term" not in st.session_state:
    st.session_state.cq2_term = "bacterial cellulose"

if "cq2_occurrence_count" not in st.session_state:
    st.session_state.cq2_occurrence_count = 3

if "cq3_publication" not in st.session_state:
    st.session_state.cq3_publication = ""

if "cq3_label" not in st.session_state:
    st.session_state.cq3_label = "PROCESS"

if "pending_query" not in st.session_state:
    st.session_state.pending_query = build_cq1_query()

if "active_question" not in st.session_state:
    st.session_state.active_question = CQ_DEFINITIONS[first_cq_name]["question"]

if "custom_question" not in st.session_state:
    st.session_state.custom_question = ""

if "custom_question_error" not in st.session_state:
    st.session_state.custom_question_error = ""

if "result_json" not in st.session_state:
    st.session_state.result_json = None

if "result_df" not in st.session_state:
    st.session_state.result_df = None

if "error_message" not in st.session_state:
    st.session_state.error_message = ""


# -----------------------------------------------------------------------------
# Sidebar browse and filter bar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="margin-bottom: 0;">
            <h2 style="margin: 0; padding: 0; color: #193743; font-size: 1.65rem; font-weight: 650; line-height: 1.3;">
                Query Explorer
            </h2>
            <p style="margin: 3px 0 14px 0; color: #475467; font-size: 0.85rem; line-height: 1.4;">
                Discover insights from scientific literature.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.selectbox(
        "Category",
        options=list(CQ_CATEGORIES.keys()),
        key="selected_category",
        on_change=queue_selected_category,
    )

    # Keep the original Selected Question card styling; make its question selectable.
    with st.container(key="selected_question_box"):
        st.markdown(
            '<div class="selected-question-label">SELECTED QUESTION</div>',
            unsafe_allow_html=True,
        )
        selected_cq = st.selectbox(
            "Selected Question",
            options=CQ_CATEGORIES[st.session_state.selected_category],
            format_func=lambda cq_name: CQ_DEFINITIONS[cq_name]["question"],
            key="selected_cq",
            on_change=queue_selected_query,
            label_visibility="collapsed",
        )

    # Streamlit 1.59 uses a single-line input; keep the native combobox
    # interactive and display its selected text in a wrapping CSS layer.
    question_css_text = json.dumps(CQ_DEFINITIONS[selected_cq]["question"])
    st.html(
        "<style>"
        ".st-key-selected_question_box { --cg-question-text: "
        + question_css_text
        + "; }"
        + """
        .st-key-selected_question_box .react-aria-ComboBox [role="group"] {
            position: relative;
            height: auto;
            min-height: 2.5rem;
            align-items: center;
        }
        .st-key-selected_question_box .react-aria-ComboBox [role="group"]::before {
            content: var(--cg-question-text);
            display: block;
            flex: 1;
            min-width: 0;
            padding: 0.5rem 0.75rem;
            white-space: normal;
            overflow-wrap: anywhere;
            line-height: 1.45;
            pointer-events: none;
        }
        .st-key-selected_question_box .react-aria-ComboBox input[role="combobox"] {
            position: absolute;
            inset: 0 auto 0 0;
            width: calc(100% - 2.5rem);
            height: 100%;
            opacity: 0;
        }
        .st-key-selected_question_box .react-aria-ComboBox input[aria-expanded="true"]:not([value=__CG_SELECTED_TEXT__]) {
            opacity: 1;
        }
        .st-key-selected_question_box [role="group"]:has(input[aria-expanded="true"]:not([value=__CG_SELECTED_TEXT__]))::before {
            visibility: hidden;
        }
        [role="listbox"][aria-label="Selected Question"] [role="presentation"] {
            position: relative !important;
            top: auto !important;
            left: auto !important;
            height: auto !important;
            width: 100% !important;
            contain: none !important;
        }
        [role="listbox"][aria-label="Selected Question"] [role="option"],
        [role="listbox"][aria-label="Selected Question"] [data-item-hl] {
            height: auto;
            white-space: normal;
            overflow-wrap: anywhere;
            overflow: visible;
            text-overflow: clip;
        }
        </style>
        """.replace("__CG_SELECTED_TEXT__", question_css_text)
    )

    if selected_cq == "Co-occurance of Terms in Paragraph":
        pair_1_term, pair_1_label = st.columns(2)
        with pair_1_term:
            st.text_input(
                "Term 1",
                key="cq1_term_1",
            )
        with pair_1_label:
            st.text_input(
                "Label 1",
                key="cq1_label_1",
            )

        pair_2_term, pair_2_label = st.columns(2)
        with pair_2_term:
            st.text_input(
                "Term 2",
                key="cq1_term_2",
            )
        with pair_2_label:
            st.text_input(
                "Label 2",
                key="cq1_label_2",
            )

    if selected_cq == "Publications by Term Frequency":
        cq2_term_column, cq2_count_column = st.columns(2)
        with cq2_term_column:
            st.text_input(
                "Term",
                key="cq2_term",
            )
        with cq2_count_column:
            st.number_input(
                "Occurrences",
                min_value=1,
                step=1,
                key="cq2_occurrence_count",
            )

    if selected_cq == "Terms by Label and Publication":
        cq3_publication_column, cq3_label_column = st.columns(2)
        with cq3_publication_column:
            st.text_input(
                "Title/DOI",
                key="cq3_publication",
            )
        with cq3_label_column:
            st.text_input(
                "Label",
                key="cq3_label",
            )

    # st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    st.button(
        "Execute",
        type="primary",
        use_container_width=True,
        on_click=queue_current_query,
    )

    # Compact acknowledgement at the bottom of the sidebar controls.
    st.markdown(
        """
        <div class="acknowledgement-box" style="margin: 2rem 0 0 0; padding: 0.6rem 0.8rem; max-width: 100%;">
            <div class="acknowledgement-title" style="font-size: 0.82rem;">Acknowledgement</div>
            <div class="acknowledgement-text" style="font-size: 0.75rem; line-height: 1.45;">
                Supported in part by USDA Forest Service (20-JV-11111124-055),
                ARS (0204-41510-001-98S), and NIFA (2021-67022-34366).
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # st.divider()
    # st.subheader("Filters")
    # st.text_input("DOI", placeholder="Enter DOI")
    # st.text_input("Title", placeholder="Enter publication title")
    # st.text_input("Authors", placeholder="Enter author name")


# -----------------------------------------------------------------------------
# Run the selected query automatically
# -----------------------------------------------------------------------------
if st.session_state.run_selected_query:
    st.session_state.run_selected_query = False
    st.session_state.error_message = ""

    try:
        with st.spinner("Querying GraphDB..."):
            result_json = run_sparql_query(st.session_state.pending_query)

        st.session_state.result_json = result_json
        st.session_state.result_df = sparql_json_to_dataframe(result_json)

    except Exception as error:
        st.session_state.result_json = None
        st.session_state.result_df = None
        st.session_state.error_message = str(error)


# -----------------------------------------------------------------------------
# Main area: output only
# -----------------------------------------------------------------------------
st.markdown(
    f'''<div class="app-title" style="display:flex;align-items:center;justify-content:center;gap:12px;">
    <svg width="34" height="34" viewBox="0 0 24 24" aria-label="Knowledge graph icon" role="img" style="flex-shrink:0;" xmlns="http://www.w3.org/2000/svg">
      <g fill="none" stroke="#176A70" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="4.5" r="2.1"/>
        <circle cx="5" cy="19" r="2.1"/>
        <circle cx="19" cy="19" r="2.1"/>
        <path d="M12 6.6 V12.5 M5 16.9 V13.5 Q5 12.5 6 12.5 H18 Q19 12.5 19 13.5 V16.9"/>
      </g>
    </svg>
    <span>{APP_TITLE}</span></div>''',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="app-subtitle">Knowledge Discovery for Cellulosic Materials</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="section-label">Output</div>', unsafe_allow_html=True)

with st.container(border=True, height=480):  # height=680
    if st.session_state.error_message:
        st.error("The query could not be completed.")
        st.code(st.session_state.error_message, language="text")

        st.markdown("**Common checks**")
        st.markdown(
            "1. Confirm that GraphDB is running.\n"
            "2. Confirm the embedded `GRAPHDB_ENDPOINT` value and repository name.\n"
            "3. Confirm that this computer can resolve the hostname `dev`.\n"
            "4. Run the same SPARQL query in the GraphDB Workbench."
        )

    elif st.session_state.result_df is not None:
        result_df: pd.DataFrame = st.session_state.result_df

        row_count = len(result_df)
        column_count = len(result_df.columns)

        metric_1, metric_2 = st.columns(2)
        metric_1.metric("Rows", row_count)
        metric_2.metric("Columns", column_count)

        table_tab, readable_tab, graph_tab, json_tab = st.tabs(
            ["Table", "Readable text", "Graph", "Raw JSON"]
        )

        with table_tab:
            if result_df.empty:
                st.info("The query ran successfully, but no rows were returned.")
            else:
                st.dataframe(
                    result_df,
                    width="stretch",
                    hide_index=True,
                    height=450,
                )

                csv_data = result_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download CSV",
                    data=csv_data,
                    file_name="cellograph_results.csv",
                    mime="text/csv",
                    width="stretch",
                )

        with readable_tab:
            render_paragraph_cards(result_df)

        with graph_tab:
            dot_graph = dataframe_to_dot(result_df)
            if dot_graph:
                st.graphviz_chart(dot_graph, width="stretch")
                if len(result_df) > 80:
                    st.caption("The graph view shows only the first 80 result rows.")
            else:
                st.info(
                    "A graph is shown when the result contains at least two "
                    "columns whose names end with 'Id'."
                )

        with json_tab:
            st.json(st.session_state.result_json, expanded=False)
            raw_json = json.dumps(
                st.session_state.result_json,
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
            st.download_button(
                "Download JSON",
                data=raw_json,
                file_name="cellograph_results.json",
                mime="application/json",
                width="stretch",
            )

    else:
        st.markdown(
            """
            <div class="output-empty">
                Select a question from Browse & Filter panel, provide input value(s), and click Execute.<br><br>
                The GraphDB result will appear here.
            </div>
            """,
            unsafe_allow_html=True,
        )
