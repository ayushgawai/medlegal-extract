from __future__ import annotations
import json, os, re, urllib.request
from datetime import date, datetime
from typing import Protocol
from .chunking import chunk_pages
from .ingestion import Page
from .resolution import resolve
from .schema import (CaseExtraction, Diagnosis, LiabilityFact, Patient,
                      Procedure, Provider, TreatmentGap, Visit)

DATE_FMTS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y")
ICD10 = re.compile(r"\b[A-TV-Z]\d{2}[0-9A-Z]?(?:\.[0-9A-Z]{1,4})?\b")
CPT = re.compile(r"\b\d{5}\b")
MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")
LIABILITY_HINTS = ("rear-ended", "rear ended", "failed to yield", "ran a red",
                   "negligen", "at fault", "failed to stop", "distracted")


def parse_date(s: str) -> date | None:
    for f in DATE_FMTS:
        try: return datetime.strptime(s.strip(), f).date()
        except ValueError: pass
    return None


def _find_dates(text: str) -> list[date]:
    out = []
    for m in re.finditer(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|"
                         r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4})\b", text):
        if (d := parse_date(m.group())): out.append(d)
    return out


class LLMProvider(Protocol):
    name: str
    cost_per_1k_tokens: float
    def extract(self, text: str) -> dict: ...


class StubProvider:
    """Deterministic offline provider: no LLM call, rules do the work."""
    name = "stub"; cost_per_1k_tokens = 0.0
    def extract(self, text: str) -> dict: return {}


class _HTTPProvider:
    cost_per_1k_tokens = 0.003
    def _post(self, url, headers, payload):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())


class AnthropicProvider(_HTTPProvider):
    name = "anthropic"
    def __init__(self, model="claude-sonnet-5-5", key=None):
        self.model, self.key = model, key or os.environ.get("ANTHROPIC_API_KEY", "")
    def extract(self, text: str) -> dict:
        data = self._post("https://api.anthropic.com/v1/messages",
            {"x-api-key": self.key, "anthropic-version": "2023-06-01"},
            {"model": self.model, "max_tokens": 1024,
             "messages": [{"role": "user", "content":
                f"Return only JSON with keys patient_name,provider,liability facts from:\n{text[:6000]}"}]})
        try: return json.loads(data["content"][0]["text"])
        except Exception: return {}


class OpenAIProvider(_HTTPProvider):
    name = "openai"
    def __init__(self, model="gpt-4o-mini", key=None):
        self.model, self.key = model, key or os.environ.get("OPENAI_API_KEY", "")
    def extract(self, text: str) -> dict:
        data = self._post("https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {self.key}"},
            {"model": self.model, "response_format": {"type": "json_object"},
             "messages": [{"role": "user", "content":
                f"Return JSON with patient_name,provider,liability facts from:\n{text[:6000]}"}]})
        try: return json.loads(data["choices"][0]["message"]["content"])
        except Exception: return {}


def get_provider(name: str = "stub") -> LLMProvider:
    return {"stub": StubProvider, "anthropic": AnthropicProvider,
            "openai": OpenAIProvider}[name]()


class HybridExtractor:
    """Regex/rules first (cheap, citable); LLM fills gaps when configured."""
    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider or StubProvider()

    def extract(self, pages: list[Page]) -> CaseExtraction:
        case = CaseExtraction()
        visits_by_key: dict[tuple, Visit] = {}
        provider = ""
        # Chunking retains page boundaries; rules then run line-by-line so
        # several visits on one page stay separate visits.
        chunks = chunk_pages(pages)
        lines = [(ln, ch) for ch in chunks for ln in ch.text.splitlines()]
        cur: Visit | None = None

        def get_visit(ch):
            nonlocal cur
            key = (provider.lower(), cur.date_of_service if cur else None)
            if cur is None:
                cur = Visit(provider=provider)
                cur.cite("provider", ch.doc_id, ch.page, provider)
            return cur

        for line, ch in lines:
            t = line.strip()
            def C(obj, field, quote=""):
                obj.cite(field, ch.doc_id, ch.page, quote or t)
            if m := re.match(r"Patient:\s*(.+)", t):
                case.patient.name = m.group(1).strip(); C(case.patient, "name", m.group(0)); continue
            if m := re.match(r"(?:DOB|Date of Birth):\s*(.+)", t):
                if d := parse_date(m.group(1)): case.patient.dob = d; C(case.patient, "dob", m.group(0))
                continue
            if m := re.match(r"Provider:\s*(.+)", t):
                provider = m.group(1).strip()
                if not any(p.name == provider for p in case.providers):
                    pr = Provider(name=provider); C(pr, "name", m.group(0)); case.providers.append(pr)
                if cur and cur.provider != provider and (cur.diagnoses or cur.procedures or cur.charges):
                    cur = None  # new provider starts a new visit context
                if cur: cur.provider = provider
                continue
            if m := re.match(r"(?:Date of Service|DOS|Visit Date):\s*(.+)", t):
                dos = parse_date(m.group(1))
                if cur and cur.date_of_service and cur.date_of_service != dos:
                    cur = None
                v = get_visit(ch); v.date_of_service = dos; C(v, "date_of_service", m.group(0)); continue
            if m := re.search(r"(?:Total(?: Charges?| Due)?|Balance Due):\s*\$?\s*([\d,]+(?:\.\d{2})?)", t, re.I):
                case.stated_total = float(m.group(1).replace(",", "")); continue
            if m := re.search(r"([A-TV-Z]\d{2}[0-9A-Z]?(?:\.[0-9A-Z]{1,4})?)\s*[-–:]\s*([^\n]+)", t):
                if ICD10.fullmatch(m.group(1)):
                    d = Diagnosis(code=m.group(1), description=m.group(2).strip()); C(d, "code", m.group(0))
                    v = get_visit(ch)
                    if d.code not in [x.code for x in v.diagnoses]: v.diagnoses.append(d)
            if m := re.search(r"(?:CPT|Procedure)[:\s]*(\d{5})\s*[-–:]?\s*([^\n]*)", t, re.I):
                p = Procedure(code=m.group(1), description=m.group(2).strip()); C(p, "code", m.group(0))
                v = get_visit(ch)
                if p.code not in [x.code for x in v.procedures]: v.procedures.append(p)
            if MONEY.search(t) and "total" not in t.lower():
                v = get_visit(ch)
                v.charges += [float(x.replace(",", "")) for x in MONEY.findall(t)]
                C(v, "charges", t)
            if any(h in t.lower() for h in LIABILITY_HINTS):
                lf = LiabilityFact(text=t, incident_date=(_find_dates(t) or [None])[0])
                # incident date is not the DOB on the same merged line; keep None unless explicit
                lf.incident_date = None; C(lf, "text", t); case.liability_facts.append(lf)
            if cur and cur not in case.visits and (cur.date_of_service or cur.diagnoses or cur.procedures or cur.charges):
                case.visits.append(cur)
        # De-dupe visits on (provider, DOS), merging their contents.
        merged: dict[tuple, Visit] = {}
        for v in case.visits:
            k = (v.provider.lower(), v.date_of_service)
            if k in merged:
                o = merged[k]
                o.diagnoses += [d for d in v.diagnoses if d.code not in [x.code for x in o.diagnoses]]
                o.procedures += [p for p in v.procedures if p.code not in [x.code for x in o.procedures]]
                o.charges += v.charges
            else:
                merged[k] = v
        case.visits = sorted(merged.values(), key=lambda v: v.date_of_service or date.min)
        if not isinstance(self.provider, StubProvider) and not case.patient.name and pages:
            extra = self.provider.extract(pages[0].text)
            if extra.get("patient_name"): case.patient.name = extra["patient_name"]
        case.diagnoses = list({d.code: d for v in case.visits for d in v.diagnoses}.values())
        case.procedures = list({p.code: p for v in case.visits for p in v.procedures}.values())
        case.total_charges = round(sum(c for v in case.visits for c in v.charges), 2)
        dates = [v.date_of_service for v in case.visits if v.date_of_service]
        for a, b in zip(sorted(dates), sorted(dates)[1:]):
            if (b - a).days > 30:
                case.treatment_gaps.append(TreatmentGap(start=a, end=b, days=(b - a).days))
        return resolve(case)
