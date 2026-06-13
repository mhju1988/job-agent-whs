"""Streamlit dashboard for the Job Agent project."""

from __future__ import annotations

import html
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import streamlit as st

from job_agent.agents.base_agent import BaseAgent
from job_agent.agents.scout_agent import ScoutAgent
from job_agent.agents.tracker_agent import InvalidTransitionError, TrackerAgent
from job_agent.agents.writer_agent import WriterAgent
from job_agent.db.client import SupabaseClient
from job_agent.tools.cover_letter_template import CoverLetterRenderer
from job_agent.tools.cv_parser import CVParseError, CVParser
from job_agent.tools.embedder import Embedder, EmbeddingServiceError

# ---------------------------------------------------------------------------
# DI: cached singletons
# ---------------------------------------------------------------------------

STATUS_COLORS: dict[str, str] = {
    "new": "gray",
    "ready_to_send": "blue",
    "applied": "violet",
    "interview": "orange",
    "offer": "green",
    "rejected": "red",
}


@st.cache_resource
def get_db() -> SupabaseClient:
    return SupabaseClient()


@st.cache_resource
def get_writer_agent(language: str = "en") -> WriterAgent:
    """Cached per-language. `language` is part of the cache key so EN and DE
    use separate Writer instances with their own renderer template binding."""
    db = get_db()
    lang_typed: Any = language  # narrow to Literal at the call site
    renderer = CoverLetterRenderer(llm_agent=BaseAgent(), language=lang_typed)
    return WriterAgent(db=db, renderer=renderer)


def _cover_letter_language() -> str:
    """Return 'en' or 'de' based on the sidebar radio selection."""
    return "de" if st.session_state.get("cover_letter_language") == "German" else "en"


@st.cache_resource
def get_tracker_agent() -> TrackerAgent:
    db = get_db()
    return TrackerAgent(db=db)


def _available_scout_sources() -> list[str]:
    """Return the list of sources that have credentials configured.

    Arbeitsagentur is always available (no key required). JSearch is added
    only when RAPIDAPI_KEY is non-blank in the environment.
    """
    from job_agent.config import get_settings

    available = ["arbeitsagentur"]
    if get_settings().rapidapi_key:
        available.append("jsearch")
    return available


@st.cache_resource
def get_scout_agent() -> ScoutAgent:
    """Build the multi-source ScoutAgent.

    Always registers Arbeitsagentur. Conditionally registers JSearch when
    RAPIDAPI_KEY is set; without it, the UI multiselect simply won't offer
    the option.
    """
    from job_agent.config import get_settings
    from job_agent.tools.arbeitsagentur_client import ArbeitsagenturClient

    db = get_db()
    clients: dict[str, Any] = {
        "arbeitsagentur": ArbeitsagenturClient.with_default_opener(),
    }
    key = get_settings().rapidapi_key
    if key:
        from job_agent.tools.jsearch_client import JSearchClient

        clients["jsearch"] = JSearchClient.with_default_opener(api_key=key)
    return ScoutAgent(clients=clients, db=db)


_SENTINEL_UUID = "00000000-0000-0000-0000-000000000000"


def run_matcher(
    db: SupabaseClient | None = None,
    *,
    rescore: bool = False,
) -> Any:
    """Trigger MatcherAgent against the single profile; surface result via Streamlit.

    Returns the MatcherResult on success, or ``None`` when the run could not
    proceed (no profile, exception). Callers that need to chain on the result
    (e.g. CV-upload auto-rescore) inspect the return; sidebar-button callers
    can ignore it.

    When ``rescore=True``, all existing ``match_scores`` rows are deleted
    before the Matcher runs — used after CV upload to force a full re-score
    against the new profile embedding. ``rescore=False`` (default) preserves
    existing scores and only processes unscored jobs.
    """
    from job_agent.agents.matcher_agent import MatcherAgent

    db = db if db is not None else get_db()
    profiles_resp = db.raw.table("profile").select("id").limit(1).execute()
    if not profiles_resp.data:
        st.error("No profile found. Upload a CV via the sidebar first.")
        return None
    profile_id: str = str(cast("list[dict[str, Any]]", profiles_resp.data)[0]["id"])

    if rescore:
        # Single-user assumption: wiping all match_scores is equivalent to wiping
        # scores for the current profile — there is only ever one profile row.
        try:
            db.raw.table("match_scores").delete().neq("id", _SENTINEL_UUID).execute()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to clear old scores before rescore: {exc}")
            return None

    try:
        with st.spinner("Scoring jobs against your profile…"):
            result = MatcherAgent(db=db).run(profile_id=profile_id)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Matcher failed: {exc}")
        return None

    st.success(f"Scored {result.scored} jobs. {len(result.errors)} errors.")
    if result.scored == 0:
        st.caption("No new jobs to score — Matcher excludes already-scored rows.")
    if result.errors:
        st.caption(f"⚠ first error: {result.errors[0]}")
    return result


def run_scout_then_matcher(
    keyword: str,
    location: str,
    max_results: int,
    sources: list[str] | None = None,
) -> None:
    """Runs Scout then Matcher unconditionally regardless of Scout result count.

    No short-circuit: if Scout fetches zero new jobs (e.g. all already in DB),
    Matcher still runs — it will simply report ``scored=0`` since there are no
    unscored jobs left.
    """
    run_scout(keyword, location, max_results, sources)
    run_matcher()


def run_scout(
    keyword: str,
    location: str,
    max_results: int,
    sources: list[str] | None = None,
) -> None:
    """Trigger a Scout run; surface result via Streamlit.

    ``sources`` filters to a subset of the configured clients. When None,
    all configured sources run.
    """
    scout = get_scout_agent()
    try:
        with st.spinner("Fetching jobs…"):
            result = scout.run(
                keyword=keyword or None,
                location=location or None,
                page_size=max_results,
                sources=sources,
            )
    except Exception as exc:  # noqa: BLE001
        # ScoutAgent.run() catches per-source exceptions internally and
        # surfaces them via result.errors — this catches only unexpected
        # failures (e.g. a bug in the agent itself or the DB upsert).
        st.error(f"Scout failed: {exc}")
        return

    st.success(f"Fetched {result.fetched} jobs, upserted {result.upserted}")
    if result.details_fetched:
        st.caption(f"Enriched {result.details_fetched} job(s) with full description.")
    if result.errors:
        # ScoutAgent formats JSearchAPIError as "...quota exceeded..." for 429s
        # (canonical message guaranteed by JSearchAPIError.__init__).
        if any("quota exceeded" in e.lower() for e in result.errors):
            st.warning("RapidAPI monthly quota exhausted — JSearch disabled until reset.")
        st.caption(f"⚠ {len(result.errors)} error(s) — first: {result.errors[0]}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate_name() -> str:
    return str(st.session_state.get("candidate_name", "Max Mustermann"))


def _run_writer(
    job_id: str,
    match_score_id: str,
    matched_skills: list[str],
) -> None:
    """Look up the profile, call WriterAgent.run with the chosen language,
    display a spinner during the run, then offer .docx downloads."""
    db = get_db()
    profiles_resp = db.raw.table("profile").select("id").limit(1).execute()
    if not profiles_resp.data:
        st.error("No profile found in the database. Please add a profile first.")
        return
    profile_id: str = str(cast("list[dict[str, Any]]", profiles_resp.data)[0]["id"])

    writer = get_writer_agent(language=_cover_letter_language())
    try:
        with st.spinner("Generating documents…"):
            result = writer.run(
                profile_id=profile_id,
                job_id=job_id,
                match_score_id=match_score_id,
                candidate_name=_candidate_name(),
                matched_skills=matched_skills,
            )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Writer failed: {exc}")
        return

    st.success("Documents ready — check Applications tab")
    # Inline download buttons for immediate feedback.
    for label, path in (
        ("Download cover letter", result.cover_letter_path),
        ("Download CV variant", result.cv_variant_path),
    ):
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            st.download_button(
                label,
                data=data,
                file_name=Path(path).name,
                key=f"dl_{label.replace(' ', '_')}_{result.application_id}",
            )
        except OSError:
            st.caption(f"{label}: file not found")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _profile_label(db: SupabaseClient) -> str:
    """Return a short label describing the current profile.

    Always returns a non-empty string — never None — so the sidebar can show
    it directly without a fallback branch. Uses ``full_name`` (added in
    migration 009) when available; falls back to "Unnamed" so the user
    knows a profile exists even when the LLM failed to extract a name.
    """
    try:
        rows = (
            db.raw.table("profile")
            .select("full_name, skills")
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            return "No profile uploaded yet"
        row = cast("dict[str, Any]", rows[0])
        name = row.get("full_name") or "Unnamed"
        skill_count = len(row.get("skills") or [])
        return f"{name} · {skill_count} skills"
    except Exception:  # noqa: BLE001 — sidebar must never crash the dashboard
        return "Profile (could not load)"


def handle_cv_upload(
    raw_bytes: bytes,
    db: SupabaseClient,
    *,
    parser: CVParser | None = None,
    embedder: Embedder | None = None,
) -> bool:
    """Parse + embed + upsert a CV. Returns True on success.

    Surfaces user-facing feedback via ``st.success`` / ``st.error``. Extracted
    as a pure-ish helper so the upload pipeline is testable without an actual
    Streamlit runtime.
    """
    try:
        try:
            parser = parser or CVParser()
            embedder = embedder or Embedder()
            profile = parser.parse_bytes(raw_bytes)
            vector = embedder.embed_text(profile.to_embedding_text())
        except CVParseError as exc:
            st.error(f"CV parse failed: {exc}")
            return False
        except EmbeddingServiceError as exc:
            st.error(f"Embedding failed: {exc}")
            return False

        row = profile.to_supabase_row()
        row["embedding"] = vector

        # The profile PK (`id`) is server-generated (gen_random_uuid()) and the
        # client never sends it, so an upsert with on_conflict="id" would always
        # take the insert branch — yielding duplicate rows on every CV upload.
        # The project is single-user by design (one profile row at a time), so
        # we delete-then-insert. UUID-impossible sentinel satisfies Supabase's
        # required-WHERE on DELETE while wiping every real row.
        db.raw.table("profile").delete().neq("id", _SENTINEL_UUID).execute()
        db.raw.table("profile").insert(row).execute()
    except Exception as exc:  # noqa: BLE001 — final safety net for the dashboard
        st.error(f"Profile update failed: {exc}")
        return False

    st.success("Profile updated.")

    # Auto-rescore: the old match_scores are stale because the embedding
    # changed with the new CV. Force a full re-score against the new profile.
    st.info("Re-scoring jobs against your new profile…")
    matcher_result = run_matcher(db, rescore=True)
    if matcher_result is None:
        # run_matcher already surfaced an st.error for any failure path;
        # the "no profile" branch is unreachable here since we just
        # inserted the profile row above. Nothing more to say.
        pass
    elif matcher_result.scored == 0 and not matcher_result.errors:
        st.info("No unscored jobs found — run Scout first to fetch new jobs.")
    elif matcher_result.errors:
        st.warning(
            f"Scored {matcher_result.scored} jobs with "
            f"{len(matcher_result.errors)} error(s)."
        )
    else:
        st.success(
            f"Profile updated and {matcher_result.scored} jobs re-scored."
        )
    return True


def _render_sidebar() -> None:
    with st.sidebar:
        st.title("Job Agent")
        st.text_input("Candidate name", value="Max Mustermann", key="candidate_name")
        st.radio(
            "Cover letter language",
            ["English", "German"],
            key="cover_letter_language",
            horizontal=True,
        )
        st.divider()

        # --- Scout settings ---
        st.markdown("**Scout settings**")
        st.text_input("Keywords", value="Python Developer", key="scout_keywords")
        st.text_input("Location", value="Berlin", key="scout_location")
        st.number_input(
            "Max results",
            min_value=5,
            max_value=50,
            value=10,
            step=5,
            key="scout_max_results",
        )
        # Multiselect — JSearch only appears when RAPIDAPI_KEY is set in .env.
        available_sources = _available_scout_sources()
        st.multiselect(
            "Sources",
            available_sources,
            default=available_sources,
            key="scout_sources",
        )
        if st.button("Run Scout Now", key="scout_run_btn"):
            selected = st.session_state.get("scout_sources") or available_sources
            run_scout(
                keyword=str(st.session_state.get("scout_keywords", "Python Developer")),
                location=str(st.session_state.get("scout_location", "Berlin")),
                max_results=int(st.session_state.get("scout_max_results", 10)),
                sources=list(selected),
            )
        if st.button("Run Matcher Now", key="matcher_run_btn"):
            run_matcher()
        if st.button("Run Both", key="scout_matcher_run_btn"):
            selected = st.session_state.get("scout_sources") or available_sources
            run_scout_then_matcher(
                keyword=str(st.session_state.get("scout_keywords", "Python Developer")),
                location=str(st.session_state.get("scout_location", "Berlin")),
                max_results=int(st.session_state.get("scout_max_results", 10)),
                sources=list(selected),
            )

        st.divider()

        # --- Update CV ---
        with st.expander("Update CV", expanded=False):
            uploaded = st.file_uploader("Upload CV (PDF)", type=["pdf"])
            if st.button("Parse & Save Profile", key="cv_upload_btn"):
                if uploaded is None:
                    st.warning("Please choose a PDF first.")
                else:
                    handle_cv_upload(uploaded.getvalue(), get_db())
            # _profile_label always returns a non-empty string (no-profile /
            # error cases produce explanatory text, not None).
            st.caption(f"Current profile: {_profile_label(get_db())}")

        st.divider()
        st.markdown("**Danger zone**")
        if st.button("Delete my data", type="primary"):
            st.session_state["delete_confirm_shown"] = True

        if st.session_state.get("delete_confirm_shown"):
            confirmed = st.checkbox("Yes, permanently delete all my data")
            if confirmed and st.button("Confirm deletion"):
                tracker = get_tracker_agent()
                summary = tracker.delete_my_data()
                st.success(
                    f"Deleted: {summary.profiles_deleted} profile(s), "
                    f"{summary.matches_deleted} match(es), "
                    f"{summary.applications_deleted} application(s), "
                    f"{summary.files_deleted} file(s)."
                )
                st.session_state["delete_confirm_shown"] = False


# ---------------------------------------------------------------------------
# Tab 1: Jobs
# ---------------------------------------------------------------------------


def _render_jobs_tab() -> None:
    st.header("Jobs")
    db = get_db()
    jobs_resp = (
        db.raw.table("jobs")
        .select("id, title, company, location, scraped_at")
        .order("scraped_at", desc=True)
        .limit(100)
        .execute()
    )
    jobs: list[dict[str, Any]] = cast("list[dict[str, Any]]", jobs_resp.data or [])
    if not jobs:
        st.info("No jobs found. Run the Scout Agent first.")
        return

    # Fetch match scores and join
    job_ids = [j["id"] for j in jobs]
    scores_resp = (
        db.raw.table("match_scores")
        .select("job_id, id, score, created_at")
        .in_("job_id", job_ids)
        .order("created_at", desc=True)
        .execute()
    )
    score_by_job: dict[str, dict[str, Any]] = {}
    # Rows arrive newest-first; first-write-wins keeps the latest score per job.
    for row in cast("list[dict[str, Any]]", scores_resp.data or []):
        jid = str(row["job_id"])
        if jid not in score_by_job:
            score_by_job[jid] = row

    table_rows = []
    for j in jobs:
        jid = str(j["id"])
        ms = score_by_job.get(jid)
        table_rows.append(
            {
                "id": jid,
                "title": j.get("title", ""),
                "company": j.get("company", ""),
                "location": j.get("location", ""),
                "score": ms["score"] if ms else None,
                "match_score_id": ms["id"] if ms else None,
                "scraped_at": j.get("scraped_at", ""),
            }
        )

    st.dataframe(
        [
            {
                "title": r["title"],
                "company": r["company"],
                "location": r["location"],
                "score": r["score"],
                "scraped_at": r["scraped_at"],
            }
            for r in table_rows
        ],
        use_container_width=True,
    )

    titles = [r["title"] or r["id"] for r in table_rows]
    selected_title = st.selectbox("Select job", titles, key="jobs_select")
    selected_row = next(
        (r for r in table_rows if (r["title"] or r["id"]) == selected_title), None
    )

    if selected_row and st.button("Generate documents", key="jobs_generate"):
        ms_id = selected_row.get("match_score_id")
        if not ms_id:
            st.warning("No match score for this job. Run the Matcher Agent first.")
        else:
            # matched_skills not available from Jobs tab — Writer will use
            # empty list (lower cover-letter personalisation). The Matches tab
            # passes the real list and produces a better letter.
            _run_writer(
                job_id=selected_row["id"],
                match_score_id=str(ms_id),
                matched_skills=[],
            )


# ---------------------------------------------------------------------------
# Tab 2: Matches
# ---------------------------------------------------------------------------


def _tag_chips(items: list[str], color: str) -> str:
    """Render a list of strings as inline-HTML pill chips of the given color.

    Colors are passed as 6-char hex (no '#'). Background gets ~13% alpha,
    text gets the full color.
    """
    # html.escape: LLM-emitted skill / gap strings are rendered into a
    # `unsafe_allow_html=True` markdown block. Without escaping, a string like
    # `</span><script>...</script>` would execute. quote=False is fine — we
    # use single-quoted attributes in the surrounding HTML.
    return " ".join(
        f"<span style='background:#{color}22;color:#{color};padding:2px 8px;"
        f"border-radius:12px;margin-right:4px;font-size:12px;"
        f"display:inline-block;'>{html.escape(s, quote=False)}</span>"
        for s in items
    )


def _render_match_card(m: dict[str, Any]) -> None:
    """Render one match row (extracted as a helper so tests can mock `st`)."""
    job_info: dict[str, Any] = cast("dict[str, Any]", m.get("jobs") or {})
    title = job_info.get("title") or "Unknown title"
    company = job_info.get("company") or "Unknown company"
    score = m.get("score")
    matched_skills_raw = m.get("matched_skills")  # None on pre-migration-008 rows
    gaps_raw = m.get("gaps")
    rationale_raw = m.get("rationale")
    ms_id = str(m["id"])
    job_id = str(m["job_id"])

    matched_skills: list[str] = list(matched_skills_raw or [])
    gaps: list[str] = list(gaps_raw or [])
    rationale = str(rationale_raw or "")[:200]

    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{title}** — {company}")

            # Fallback: no analysis at all (legacy row from before
            # migration 008 was applied / before LLM gap analysis ran).
            if (
                matched_skills_raw is None
                and gaps_raw is None
                and rationale_raw is None
            ):
                st.caption(
                    "No analysis available — re-run Matcher to score this job."
                )
            else:
                if matched_skills:
                    st.markdown(
                        "**Matched skills:** " + _tag_chips(matched_skills, "16a34a"),
                        unsafe_allow_html=True,
                    )
                if gaps:
                    st.markdown(
                        "**Gaps:** " + _tag_chips(gaps, "d97706"),
                        unsafe_allow_html=True,
                    )
                if rationale:
                    st.caption(rationale)

        with col2:
            st.metric("Score", score)
            if st.button("Prepare application", key=f"match_apply_{ms_id}"):
                _run_writer(
                    job_id=job_id,
                    match_score_id=ms_id,
                    matched_skills=matched_skills,
                )


SORT_HIGH_LOW = "Score (high → low)"
SORT_LOW_HIGH = "Score (low → high)"
SORT_RECENT = "Most recent"
_SORT_OPTIONS = [SORT_HIGH_LOW, SORT_LOW_HIGH, SORT_RECENT]


def _filter_and_sort_matches(
    matches: list[dict[str, Any]],
    threshold: int,
    sort_mode: str,
) -> list[dict[str, Any]]:
    """Apply score-threshold filter then sort. Extracted for testability.

    Rows with ``score is None`` (unscored — should not exist in production
    since the column is NOT NULL, but defensive) are excluded from every
    threshold filter and sink to the bottom of every score-based sort via
    a ``float("-inf")`` sort key. This prevents an unscored job from
    masquerading as a zero-scored one.

    Sort modes follow ``_SORT_OPTIONS`` — unknown modes fall through to
    the high→low default.
    """
    # Explicit `is not None` so unscored jobs (None) are dropped at any
    # threshold, including threshold=0.
    filtered = [
        m for m in matches if m.get("score") is not None and m["score"] >= threshold
    ]
    # After the filter every surviving row has a real numeric score, but
    # the sort key stays defensive with -inf in case future code paths
    # bypass the filter.
    def _score_key(m: dict[str, Any]) -> float:
        s = m.get("score")
        return float(s) if s is not None else float("-inf")

    if sort_mode == SORT_LOW_HIGH:
        return sorted(filtered, key=_score_key)
    if sort_mode == SORT_RECENT:
        # Newest first; rows without created_at sort to the end.
        return sorted(filtered, key=lambda m: str(m.get("created_at") or ""), reverse=True)
    # Default: SORT_HIGH_LOW — None sinks to bottom via -inf.
    return sorted(filtered, key=_score_key, reverse=True)


def _render_matches_tab() -> None:
    st.header("Matches")
    db = get_db()
    matches_resp = (
        db.raw.table("match_scores")
        .select(
            "id, job_id, score, matched_skills, gaps, rationale, created_at, "
            "jobs(title, company)"
        )
        .order("score", desc=True)
        .limit(50)
        .execute()
    )
    matches: list[dict[str, Any]] = cast("list[dict[str, Any]]", matches_resp.data or [])
    if not matches:
        st.info("No match scores found. Run the Matcher Agent first.")
        return

    # Filter + sort controls
    threshold = int(
        st.slider(
            "Minimum score",
            min_value=0,
            max_value=100,
            value=50,
            step=5,
            key="score_threshold",
        )
    )
    sort_mode = str(
        st.selectbox("Sort by", _SORT_OPTIONS, key="score_sort")
    )

    visible = _filter_and_sort_matches(matches, threshold, sort_mode)
    st.caption(
        f"Showing {len(visible)} of {len(matches)} matches (score ≥ {threshold})"
    )

    for m in visible:
        _render_match_card(m)


# ---------------------------------------------------------------------------
# Tab 3: Applications
# ---------------------------------------------------------------------------


def _render_applications_tab() -> None:
    st.header("Applications")
    db = get_db()
    apps_resp = (
        db.raw.table("applications")
        .select(
            "id, job_id, job_title, job_company, status, "
            "cover_letter_path, cv_variant_path, follow_up_at, applied_at"
        )
        .order("created_at", desc=True)
        .execute()
    )
    apps: list[dict[str, Any]] = cast("list[dict[str, Any]]", apps_resp.data or [])
    if not apps:
        st.info("No applications yet. Generate documents from the Jobs or Matches tab.")
        return

    now_utc = datetime.now(UTC)
    tracker = get_tracker_agent()

    for app in apps:
        app_id = str(app["id"])
        status = str(app.get("status") or "new")
        job_title = str(app.get("job_title") or "Unknown")
        job_company = str(app.get("job_company") or "Unknown")
        cover_path = app.get("cover_letter_path")
        cv_path = app.get("cv_variant_path")
        follow_up_at_raw: str | None = app.get("follow_up_at")

        color = STATUS_COLORS.get(status, "gray")

        # Check follow-up flag
        follow_up_flag = ""
        if follow_up_at_raw:
            try:
                fu_dt = datetime.fromisoformat(follow_up_at_raw)
                if fu_dt.tzinfo is None:
                    fu_dt = fu_dt.replace(tzinfo=UTC)
                if fu_dt <= now_utc:
                    follow_up_flag = " \U0001f514"
            except ValueError:
                pass

        with st.container(border=True):
            st.markdown(
                f"**{job_title} @ {job_company}**{follow_up_flag}  "
                f":{color}[**{status}**]"
            )

            # Download buttons
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                if cover_path:
                    try:
                        with open(cover_path, "rb") as fh:
                            data = fh.read()
                        st.download_button(
                            "Download cover letter",
                            data=data,
                            file_name=Path(cover_path).name,
                            key=f"dl_cover_{app_id}",
                        )
                    except OSError:
                        st.caption("File not found.")
                else:
                    st.caption("File not found.")

            with dl_col2:
                if cv_path:
                    try:
                        with open(cv_path, "rb") as fh:
                            data = fh.read()
                        st.download_button(
                            "Download CV variant",
                            data=data,
                            file_name=Path(cv_path).name,
                            key=f"dl_cv_{app_id}",
                        )
                    except OSError:
                        st.caption("File not found.")
                else:
                    st.caption("File not found.")

            # Transition buttons
            btn_cols = st.columns(5)
            transitions: list[tuple[str, str, list[str]]] = [
                ("Mark Ready", "ready_to_send", ["new"]),
                ("Mark Applied", "applied", ["ready_to_send"]),
                ("Got Interview", "interview", ["applied"]),
                ("Got Offer", "offer", ["interview"]),
                ("Rejected", "rejected", ["applied", "interview", "offer"]),
            ]
            for idx, (label, target, valid_from) in enumerate(transitions):
                with btn_cols[idx]:
                    if status in valid_from and st.button(
                        label, key=f"trans_{app_id}_{target}"
                    ):
                        try:
                            tracker.transition(app_id, target)
                            st.rerun()
                        except InvalidTransitionError as exc:
                            st.error(str(exc))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="Job Agent", page_icon=":briefcase:", layout="wide")
    _render_sidebar()
    jobs_tab, matches_tab, applications_tab = st.tabs(
        ["Jobs", "Matches", "Applications"]
    )
    with jobs_tab:
        _render_jobs_tab()
    with matches_tab:
        _render_matches_tab()
    with applications_tab:
        _render_applications_tab()


if __name__ == "__main__":
    main()
