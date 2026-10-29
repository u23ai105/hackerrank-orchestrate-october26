import re
from enum import Enum


class RequestIntent(str, Enum):
    DELETION_REQUESTED = "DELETION_REQUESTED"
    NOT_A_DELETION_REQUEST = "NOT_A_DELETION_REQUEST"
    AMBIGUOUS = "AMBIGUOUS"


_DASHES = str.maketrans({
    "-": " ",
    "\u2010": " ",
    "\u2011": " ",
    "\u2012": " ",
    "\u2013": " ",
    "\u2014": " ",
    "\u2212": " ",
})

_DELETE_VERB = (
    r"(?:delete|deleted|deleting|erase|erased|erasing|"
    r"wipe|wiped|wiping|purge|purged|purging|"
    r"remove(?!\s+(?:me\s+)?from\s+(?:the\s+|all\s+)?(?:marketing|promotional|newsletter|mailing|lists?)\b)|"
    r"removed|removing|destroy|destroyed|destroying)"
)

_TARGET = (
    r"(?:(?:my|the|this|all|any|a|an)\s+)?"
    r"(?:personal\s+)?"
    r"(?:account|profile|personal data|data|records|"
    r"information|details)"
)

_FIELD = (
    r"(?:mobile number|telephone number|phone number|email address|"
    r"last name|first name|surname|mobile|telephone|phone|"
    r"email|address|profile details|profile|name)"
)


def _normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.translate(_DASHES)
    return re.sub(r"\s+", " ", text).strip()


_EXPLICIT_NEGATION = [
    re.compile(
        r"\b(?:do not|don't|dont|never)\s+"
        r"(?:delete|erase|wipe|purge|remove|destroy|close)\b"
    ),
    re.compile(
        r"\b(?:do not|don't|dont)\s+"
        r"(?:want|wish|need|intend)\b.{0,80}\b"
        r"(?:delete|deleting|deletion|erase|erasure|"
        r"remove|removal|wipe|purge|close)\b"
    ),
    re.compile(
        r"\b(?:no|not a|not an|not|am not|is not|are not|isn't)\s+"
        r"(?:a\s+)?(?:request\s+(?:for|to)\s+|asking\s+for\s+)?"
        r"(?:delete|erase|wipe|purge|remove|destroy|close|"
        r"account\s+deletion|data\s+deletion|deletion)\b"
    ),
    re.compile(
        r"\bwithout\s+(?:deleting|erasing|removing|wiping|purging)\b"
    ),
    re.compile(
        r"\bno\s+(?:quiero|solicito|pido|deseo)\b.{0,80}\b"
        r"(?:eliminar|borrar|suprimir|eliminacion|eliminación)\b"
    ),
    re.compile(
        r"\bje\s+ne\s+(?:veux|souhaite|demande)\s+pas\b.{0,80}\b"
        r"(?:supprimer|suppression|effacer|effacement)\b"
    ),
    re.compile(
        r"\b(?:não quero|nao quero|não solicito|nao solicito)\b"
        r".{0,80}\b(?:excluir|exclusão|exclusao|apagar|remover)\b"
    ),
    re.compile(r"削除しないで|削除は不要|削除を希望しません"),
    re.compile(r"삭제하지 말아|삭제를 원하지 않"),
]


_DELETION_PATTERNS = [
    # Delete/erase/remove a data-bearing target, in either word order.
    re.compile(r"\b" + _DELETE_VERB + r"\b.{0,100}\b" + _TARGET + r"\b"),
    re.compile(r"\b" + _TARGET + r"\b.{0,100}\b" + _DELETE_VERB + r"\b"),

    # Direct requests for deletion, including hyphen-normalized forms.
    re.compile(
        r"\b(?:request|requesting|asked|asking|ask|want|wants|"
        r"wanted|need|needs|wish|wishes|intend|intending)\b"
        r".{0,80}\b(?:deletion|erasure|removal|to delete|"
        r"to erase|to remove|to purge)\b"
        r".{0,80}\b(?:account|profile|personal data|data|"
        r"records|information)\b"
    ),
    re.compile(
        r"\b(?:account|data|profile)\s+deletion\b(?!\s+(?:policy|rules|faq|question|inquiry)\b)"
    ),
    re.compile(
        r"\b(?:deletion|erasure|removal)\b.{0,50}\b"
        r"(?:of|for)\b.{0,30}\b"
        r"(?:my|the|this)?\s*(?:account|profile|data|records)\b"
    ),
    re.compile(r"\bright to be forgotten\b"),
    re.compile(r"\b(?:delete|erase)\s+me\b"),
    re.compile(
        r"\bremove\s+me\b(?!\s+from\s+(?:the\s+|all\s+)?(?:marketing|promotional|newsletter|mailing|lists?)\b)"
    ),
    re.compile(
        r"\bclose\s+(?:(?:my|the|this|an?)\s+)?account\b"
    ),

    # Spanish: clearly expressed account/data deletion or erasure.
    re.compile(
        r"\b(?:eliminar|eliminacion|eliminación|borrar|borrado|"
        r"suprimir|supresion|supresión)\b.{0,80}\b"
        r"(?:mi\s+|la\s+|los\s+|mis\s+)?"
        r"(?:cuenta|datos|perfil|informacion|información)\b"
    ),
    re.compile(
        r"\b(?:cuenta|datos|perfil|informacion|información)\b"
        r".{0,80}\b(?:eliminacion|eliminación|borrado|"
        r"supresion|supresión)\b"
    ),

    # French: account/profile/data deletion.
    re.compile(
        r"\b(?:supprimer|suppression|effacer|effacement)\b"
        r".{0,80}\b(?:compte|données|donnees|profil|informations)\b"
    ),
    re.compile(
        r"\b(?:compte|données|donnees|profil|informations)\b"
        r".{0,80}\b(?:suppression|effacement)\b"
    ),

    # Portuguese: account/profile/data deletion.
    re.compile(
        r"\b(?:excluir|exclusão|exclusao|apagar|eliminar|"
        r"remoção|remocao|remover)\b.{0,80}\b"
        r"(?:conta|dados|perfil|informações|informacoes)\b"
    ),
    re.compile(
        r"\b(?:conta|dados|perfil|informações|informacoes)\b"
        r".{0,80}\b(?:exclusão|exclusao|remoção|remocao)\b"
    ),

    # Japanese and Korean: common explicit account/data deletion forms.
    re.compile(
        r"アカウント.{0,40}削除|削除.{0,40}アカウント|"
        r"データ.{0,30}削除|削除.{0,30}データ|"
        r"個人情報.{0,30}削除"
    ),
    re.compile(
        r"계정.{0,40}삭제|삭제.{0,40}계정|"
        r"데이터.{0,30}삭제|삭제.{0,30}데이터|"
        r"개인정보.{0,30}삭제"
    ),
]


_FOLLOWUP_DELETION_PATTERNS = [
    # An explicit request to investigate or finish a deletion.
    re.compile(
        r"\b(?:investigate|check|verify|confirm|finish|complete|"
        r"resume|continue)\b.{0,120}\b"
        r"(?:the\s+)?(?:account\s+)?"
        r"(?:deletion|erasure|removal)\b"
    ),

    # Verify that a profile, account, data, or search result has
    # reached a deletion-related state.
    re.compile(
        r"\b(?:check|verify|confirm|investigate)\b.{0,120}\b"
        r"(?:my\s+|the\s+|this\s+)?"
        r"(?:account|profile|personal data|data|search result)\b"
        r".{0,45}\b(?:is|was|are|were|has been|have been|"
        r"remains?|still exists?)\b.{0,25}\b"
        r"(?:gone|deleted|removed|absent|missing|"
        r"no longer present|no longer visible)\b"
    ),

    # A request to investigate a resource that still exists or
    # remains discoverable after a purported deletion.
    re.compile(
        r"\b(?:account|profile|personal data|data|search result)\b"
        r".{0,80}\b(?:still exists?|still existed|"
        r"can still be found|is still visible|remains discoverable)\b"
        r".{0,120}\b(?:investigate|check|verify|confirm|"
        r"finish|complete|remove|delete)\b"
    ),
]


_NON_DELETION_PATTERNS = [
    # Match a corrective action directly connected to a field.
    # Do not use broad patterns such as "correct ... email" across
    # arbitrary text: "apply the correct treatment" is not an update.
    re.compile(
        r"\b(?:update|change|correct|fix|edit)\s+"
        r"(?:(?:my|the|this|a|an)\s+)?"
        + _FIELD + r"\b"
    ),
    re.compile(
        r"\b" + _FIELD
        + r"\s+(?:is|was)\s+(?:wrong|incorrect|misspelled|"
          r"outdated|incorrectly spelled)\b"
    ),
    re.compile(
        r"\b" + _FIELD
        + r"\b.{0,20}\b(?:needs to be|should be|must be)\s+"
        r"(?:updated|changed|corrected|fixed|edited)\b"
    ),

    # An outdated mobile, telephone, or email field requested to replace or update.
    re.compile(
        r"\b(?:mobile(?:\s+number)?|phone(?:\s+number)?|"
        r"telephone(?:\s+number)?|email(?:\s+address)?|"
        r"address|surname|last name|first name)\b"
        r".{0,60}\b(?:is|was)\b.{0,25}\b"
        r"(?:out of date|outdated|incorrect|wrong|misspelled)\b"
        r".{0,120}\b(?:replace|update|change|correct|fix|edit)\b"
    ),

    # Document copies (invoices, receipts, statements, bills)
    re.compile(
        r"\b(?:need|want|request|send|provide|get|obtain)\b"
        r".{0,60}\b(?:a\s+)?copy\b.{0,80}\b"
        r"(?:invoices?|receipts?|statements?|bills?)\b"
    ),

    # Explicit preservation of account, profile, records in place / active
    re.compile(
        r"\b(?:leave|keep|retain)\b.{0,50}\b"
        r"(?:my\s+|the\s+|this\s+)?"
        r"(?:account|profile|purchase history|records)\b"
        r".{0,30}\b(?:in place|active|unchanged|as is)\b"
    ),

    # Marketing preferences only.
    re.compile(
        r"\b(?:opt out|opt me out|unsubscribe|stop receiving|"
        r"remove me from|remove my email from)\b.{0,80}\b"
        r"(?:marketing|promotional|newsletter|mailing list|"
        r"marketing emails|marketing lists)\b"
    ),

    # Data access/export without an associated deletion request.
    re.compile(
        r"\b(?:export|download|access|obtain|get|send|provide|"
        r"request access to)\b.{0,80}\b"
        r"(?:my\s+)?(?:personal\s+)?"
        r"(?:data|information|records|copy)\b"
    ),
]


def classify_request_intent(request_text: str) -> RequestIntent:
    """
    Deterministically classify the intent expressed by request_text.

    Precedence:
      1. Explicitly negated deletion -> NOT_A_DELETION_REQUEST.
      2. Clear deletion intent -> DELETION_REQUESTED.
      3. Follow-up deletion verification / audit -> DELETION_REQUESTED.
      4. Clear non-deletion task -> NOT_A_DELETION_REQUEST.
      5. Otherwise -> AMBIGUOUS.

    AMBIGUOUS must not automatically become NOT_APPLICABLE.
    """
    text = _normalize(request_text)

    if not text:
        return RequestIntent.AMBIGUOUS

    if any(p.search(text) for p in _EXPLICIT_NEGATION):
        return RequestIntent.NOT_A_DELETION_REQUEST

    if any(p.search(text) for p in _DELETION_PATTERNS):
        return RequestIntent.DELETION_REQUESTED

    if any(p.search(text) for p in _FOLLOWUP_DELETION_PATTERNS):
        return RequestIntent.DELETION_REQUESTED

    if any(p.search(text) for p in _NON_DELETION_PATTERNS):
        return RequestIntent.NOT_A_DELETION_REQUEST

    return RequestIntent.AMBIGUOUS
