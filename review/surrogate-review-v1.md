# Surrogate Review v1

## Review disposition

**REWORK**

The layered model is directionally sound, but this first prototype is not ready
to replace the current reader entry. The smallest next action is to make the
candidate-to-area mapping and unresolved-reason projection explicit for real
observed concepts, then rerun the representative cases and cross-concept checks.

## Findings

### Accepted elements

- Business areas are separate from concept details.
- Attribute expression, field attribute, qualifier, and physical implementation
  are separate sections.
- Wiki candidates retain title/path evidence and cannot publish hierarchy.
- The skeleton produces no unsupported concept or physical fact by itself.
- Candidate, review decision, and published-entry layers are distinct.

### Required rework

1. **Business-area mapping is still mostly a contract.** The prototype names the
   full skeleton but does not yet show a deterministic, evidence-bearing mapping
   for the real 1,375 observed concepts.
2. **Role and subject boundaries need corpus evidence.** Counterparty, buyer,
   seller, trader, client and institution require separate role/context handling,
   not only labels in a configuration file.
3. **Lifecycle and result measures need counterexamples.** Settlement, reset,
   close-out and valuation-rate expressions must not become events merely because
   their labels contain lifecycle words.
4. **Unresolved reasons need real counts and examples.** A schema and fixture are
   insufficient; the full run must report the composition of the unresolved queue.
5. **Reader acceptance is still open.** This review is an engineering surrogate
   disposition and is not user acceptance or business acceptance.

## Counterexamples checked

- `结算汇率` / `重置汇率`: rate/measure candidate with lifecycle context, not an
  event solely from the prefix.
- `交易对手编号`: counterparty concept + identifier axis, not only generic
  identifier.
- `买方` / `卖方` / `甲方` / `乙方`: role candidates, not four independent
  business-subject branches.
- `动态名义本金`: attribute expression with state qualifier, not a new
  unrelated business concept.
- Wiki title containing TRS or an acceptance/test branch: bounded context, not
  proof of field business responsibility.

## Next review gate

Do not mark the new navigation entry as reader-ready until the real observed
concept inventory is mapped or explicitly left in a reasoned queue, the five
counterexample groups are replayed, and a second concept/configuration confirms
that the method is not nominal-principal-specific.
