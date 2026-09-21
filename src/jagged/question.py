from msgspec import Struct


class QuestionSpec(Struct, frozen=True):
    """A Noul as plain data, so arms can rewrite it and tests can diff it.

    `boundary` is the explicitly-stated edge case the docs recommend including.
    The docs put it in the criteria, not the instruction string: "state the exact
    condition in the `instructions`. Be specific. Put boundary cases in the
    criteria." It stays its own field so the `literal` arm can drop it
    generically, and so substrates own their wording without importing
    `jagged.conditions`.

    `boundary_key` exists because which side an edge case narrows is the
    substrate's business. AfD's boundary ("a redirect is not a deletion") narrows
    the false side; another substrate's might narrow the true side.
    """

    instructions: str
    criteria: dict[str, str] | None = None
    boundary: str = ""
    boundary_key: str = "false"

    @property
    def rendered_criteria(self) -> dict[str, str] | None:
        """Criteria with the boundary folded into its side. None stays None."""
        if self.criteria is None:
            return None
        merged = dict(self.criteria)
        if self.boundary:
            existing = merged.get(self.boundary_key, "")
            merged[self.boundary_key] = f"{existing} {self.boundary}".strip()
        return merged

    def to_noul(self) -> dict:
        """The question object the gateway accepts, not an SDK Noul."""
        payload = {"type": "boolean", "instructions": self.instructions}
        criteria = self.rendered_criteria
        if criteria is not None:
            payload["criteria"] = criteria
        return payload
