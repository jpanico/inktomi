# Basic processing pipeline

A high-level overview of the core data processing pipeline that is utilized by the scripts in this project.

1. `FetchSpec`: user supplies a qualifier (`NodeFetchAnchor`) that identifies the anchor (starting) node in the Roam Datomic query, as well as some join semantics (`include_refs`)
2. *"Raw" result*: `FetchSpec` is used to query the Roam Datomic DB., which results in a list of Datomic pull-blocks (`NodeFetchResult.raw_result`)
3. `NodeNetwork`: Each raw result pull-block is parsed into a `RoamNode`, validating it using the Pydantic model specified on `RoamNode`
4. `NodeTree`: build a `NodeTree` (DAG) from `NodeNetwork`, using the `RoamNode` identified in `NodeFetchAnchor` as the root of the tree. Apply all referential integrity constraints specified in the Pydantic `@model_validator` `_validate_is_tree`.
5. `VertexTree`: "transcribe" the `NodeTree` into a Roam agnostic `VertexTree`, via `roam_transcribe.py::transcribe`. During transcription, Roam flavored Markdown (Roamdown) is translated into CommonMark.
6. **Output** (two mutually exclusive paths, controlled by `--format`):
   - **Markdown** (`md_rendering.py`): render the `VertexTree` to a CommonMark string, then either write a plain `.md` file (`--no-bundle`) or fetch Cloud Firestore image assets and write a self-contained `.mdbundle/` directory (`--bundle`).
   - **PDF** (`pdf_rendering.py`): fetch Cloud Firestore image assets via `FetchRoamAsset`, build a Panflute `Doc` (Pandoc object model) directly from the `VertexTree`, serialize to Pandoc JSON, and invoke Pandoc + Typst to produce a `.pdf` file.

## Diagram

```mermaid
flowchart TD
    USER["<b>User Input</b><br/>qualifier string<br/><i>page title or node UID</i>"]

    ANCHOR["<b>NodeFetchAnchor</b><br/>qualifier + kind<br/><i>PAGE_TITLE | NODE_UID</i>"]

    SPEC["<b>NodeFetchSpec</b><br/>anchor · include_refs · include_node_tree"]

    QUERY["<b>Roam Datomic DB</b><br/>Datalog pull-block query<br/><i>via Roam Local API</i>"]

    RAW["<b>Raw Result</b><br/>NodeFetchResult.raw_result<br/><i>list[list[dict]] — one pull-block per row</i>"]

    NETWORK["<b>NodeNetwork</b><br/>list[RoamNode]<br/><i>Pydantic model validation per pull-block</i>"]

    TREE["<b>NodeTree</b><br/>rooted DAG<br/><i>referential integrity via _validate_is_tree</i>"]

    VTREE["<b>VertexTree</b><br/>Roam-agnostic vertex tree<br/><i>Roamdown → CommonMark  ·  roam_transcribe.py</i>"]

    MD["<b>CommonMark string</b><br/>md_rendering.py"]

    BUNDLE["<b>.mdbundle/</b><br/>CommonMark + fetched images<br/><i>roam_md_bundle.py</i>"]

    MDFILE["<b>.md file</b><br/>plain CommonMark"]

    PDF["<b>.pdf file</b><br/>Panflute Doc → Pandoc JSON → Typst<br/><i>pdf_rendering.py</i>"]

    USER  -->|"qualify()"| ANCHOR
    ANCHOR -->|"NodeFetchSpec(...)"| SPEC
    SPEC  -->|"FetchRoamNodes.fetch_roam_nodes()"| QUERY
    QUERY -->|"raw JSON response"| RAW
    RAW   -->|"RoamNode.model_validate() × N"| NETWORK
    NETWORK -->|"build_tree(anchor)"| TREE
    TREE  -->|"transcribe()"| VTREE
    VTREE -->|"render_md() --format markdown"| MD
    MD    -->|"--bundle"| BUNDLE
    MD    -->|"--no-bundle"| MDFILE
    VTREE -->|"render_pdf() --format pdf"| PDF
```
