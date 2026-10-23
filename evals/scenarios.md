# Platform Baseline Scenarios

These scenarios check that the audit skills apply the platform baseline (`shared/os11-platform-baseline.md`) correctly: no false positives where OutSystems already provides a control, and no suppressed findings where it doesn't.

## How to Run

Build a small test module in Service Studio that matches a scenario's **Setup**, start the MCP server, and run the named skill. Compare the output with **Expected**. A scenario passes only when the finding (or its absence) **and** the section it lands in both match.

To re-check after editing the baseline, run every scenario for the skill you changed.

## Security

| ID | Setup | Expected |
| :--- | :--- | :--- |
| S01 | Reactive app, Users provider. Login screen calls `User_Login`. | No brute-force finding. *Platform Controls Relied On* lists login throttling (SEC-BRUTE-FORCE). *Verify in Environment* lists the Users brute-force site properties. |
| S02 | Login action reads `AppUser.PasswordHash` with an Aggregate, compares it, then calls `Login(UserId)`. | Confirmed brute-force finding naming the action. **Platform control considered** says the flow bypasses the user provider. |
| S03 | App authenticates through an external identity provider with no local password login. | No brute-force finding. *Verify in Environment* lists the identity provider's lockout policy. |
| S04 | Public Server Action `Order_Delete` deletes records, has no `Check<Role>Role`, and is called only from a screen restricted to the Admin role. | Finding for a missing role check. Screen roles are not cited as a mitigation (SEC-AUTHZ). |
| S05 | Advanced SQL with `Expand Inline = Yes`, value built from a screen input, no `EncodeSql`. | Confirmed SQL injection finding. |
| S06 | Advanced SQL with `Expand Inline = Yes` for `ORDER BY`, value chosen from a fixed list in logic. | No SQL injection finding. The parameter appears under *Platform Controls Relied On* as reviewed. |
| S07 | Advanced SQL with `Expand Inline = Yes` for an `IN (...)` list, value wrapped in `EncodeSql`. | Finding: `EncodeSql` doesn't protect `IN` lists; recommends `BuildSafe_InClauseIntegerList` or `BuildSafe_InClauseTextList`. |
| S08 | Ordinary Reactive screens with escaped Expressions and Aggregates, no Expand Inline. | No CSRF, XSS, SQL injection, or session-fixation findings. |
| S09 | Client Variable `AuthToken` stores an API token. | Finding for sensitive data in browser storage (SEC-SESSION). |

## Performance

| ID | Setup | Expected |
| :--- | :--- | :--- |
| P01 | Aggregate filters on `Order.CustomerId`, a reference attribute with Delete Rule `Protect`. | No missing-index finding. |
| P02 | Same filter, but the Delete Rule is `Ignore`. | Missing-index finding on `Order.CustomerId`. |
| P03 | Reactive app with Client Variables only. | No "heavy session variables" finding. |
| P04 | Advanced SQL on a growing table with `Max Records = 50` and no `TOP` or `OFFSET ... FETCH`. | Unbounded query finding noting that Max Records doesn't change the SQL. |

## Maintainability

| ID | Setup | Expected |
| :--- | :--- | :--- |
| M01 | `AllExceptions` handler with `Log Error = Yes` that ends at `End` with no `LogMessage`. | No swallowed-exception finding. |
| M02 | Same handler with `Log Error = No`. | Swallowed-exception finding. |
| M03 | Module with one unhidden and one hidden TrueChange warning. | One finding for the unhidden warning only, citing its text. |
