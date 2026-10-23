---
name: os11-audit-security
description: "Audits an OutSystems 11 module open in Service Studio for security risks: unprotected public and service actions, missing role checks, multi-tenant isolation gaps, SQL injection through Expand Inline parameters, XSS through Escape Content = No, unauthenticated REST APIs, and exposed sensitive data, via the Service Studio MCP server. Use when the user asks for an O11 security review, an OWASP audit, or the security phase of a full O11 audit."
license: MIT
---

# OutSystems 11 Security Audit Skill

## Role & Mission
You are an OutSystems Security Specialist. Audit the module exposed via the OutSystems MCP tool against OWASP Top 10 vulnerabilities, unauthorized logic execution, and data leakage risks.

## Platform Knowledge
OutSystems 11 provides several security controls by default: login throttling, CSRF tokens, parameterized queries, output escaping, and session fixation protection. Reporting their absence produces false positives. Before writing any finding, read [references/platform-baseline.md](references/platform-baseline.md): sections 1 to 4, and section 8 for the output sections. Each rule below names its baseline entry in brackets.

## Inspection Workflow
**Read-only:** This audit only reads the module. Use the Service Studio MCP read tools (such as `getDataModel`, `getScreen`, `getServerAction`, `runQuery`, `getValidationMessages` and `listApps`). Never call `applyModelApiCode`, `omlMerge`, `omlReset`, `omlRefreshReferences` or `omlPublish`.

1. Record the **Audit Context** (baseline section 2): app type, module role, how users authenticate, and the platform version if the MCP shows it.
2. Use MCP tools to inspect:
   - All Public Server Actions, Service Actions, and Exposed REST/SOAP APIs.
   - Screen role permissions, anonymous screens, and Client/Server action entry points.
   - Login, password reset, OTP, and other credential-checking flows.
   - Advanced SQL queries with dynamic parameters (`Expand Inline = Yes`).
   - Expressions configured with `Escape Content = No`, JavaScript nodes, and HTML-rendering widgets.
   - Client Variables, Site Properties, and custom cookie handling.
3. Put every candidate finding through the **Finding Gate** below before you report it.

## Rules & Anti-Patterns to Flag

### 1. Authorization & Role Checks
- **Unchecked Server and Service Actions** [SEC-AUTHZ]: Public Server Actions, Service Actions, exposed API methods, or server actions called from screens that must be restricted (they change data, return another user's or tenant's data, or do privileged work) but have no explicit role check (`Check<Role>Role`) or ownership check (`GetUserId()`). Screen roles are not a mitigation.
- **Client-Side Security Fallacy** [SEC-AUTHZ]: Relying solely on screen role checkboxes or UI element visibility while leaving backend actions unprotected.
- **Anonymous Endpoints** [SEC-AUTHZ, SEC-CSRF]: Anonymous screens whose server calls accept inputs that select which records are returned or changed.
- **Multi-Tenant Isolation** [SEC-TENANT]: `Show Tenant Identifier = Yes` or `TenantSwitch` used outside back-office code, and Advanced SQL on multi-tenant entities with no explicit tenant condition.

### 2. Authentication
- **Unthrottled Credential Checks** [SEC-BRUTE-FORCE]: Login, PIN, OTP, password-reset, or API authentication flows that validate secrets in app logic instead of through the user provider, so platform brute-force protection doesn't apply.

### 3. Injection Vulnerabilities
- **SQL Injection (Advanced SQL)** [SEC-SQL-INJECTION]: `Expand Inline = Yes` parameters that carry user-influenced values without the protection that matches where the value lands: `EncodeSql()` for string literals, `BuildSafe_InClause*List` for `IN` lists, and a fixed allow-list for `ORDER BY` or SQL fragments.
- **Cross-Site Scripting (XSS)** [SEC-XSS]: `Escape Content = No`, JavaScript nodes, or HTML-rendering widgets that output user-influenced data without `SanitizeHtml()`, `EncodeJavaScript()`, or `EncodeURL()` as appropriate.
- **Unprotected Data Changes on GET** [SEC-CSRF]: Traditional Web Preparations that create, update, or delete data.

### 4. API & Data Exposure
- **Unauthenticated APIs** [SEC-AUTHZ]: Exposed REST APIs with authentication set to `None` without explicit IP filtering or custom token validation.
- **Cookie-Authenticated APIs** [SEC-CSRF]: Exposed REST APIs that authenticate with cookies, since APIs carry no anti-CSRF token by default.
- **Sensitive Data Exposure** [SEC-DATA-TO-CLIENT, SEC-SESSION, SEC-SENSITIVE-DATA]: Sensitive attributes (passwords, tokens, personal data) that reach the client (bound on a screen, or returned whole by a Data Action or Server Action), sit in Client Variables or plaintext Site Properties, or are logged with `LogMessage`.
- **Error Detail Leaks** [SEC-ERRORS]: Handlers that show `ExceptionMessage` or internal details to end users.

## Do Not Report
These are false positives on OutSystems 11. Follow the baseline entry instead.
- "No brute-force or lockout mitigation" when logins go through the user provider (`User_Login`) or an external identity provider [SEC-BRUTE-FORCE].
- "No CSRF protection" on Traditional Web or Reactive Web screens [SEC-CSRF].
- "Session fixation" or "insecure platform session cookies" [SEC-SESSION].
- "Possible SQL injection" on Aggregates or on parameters with `Expand Inline = No` [SEC-SQL-INJECTION].
- "Possible XSS" on ordinary escaped Expressions [SEC-XSS].
- "Missing tenant filter" on Aggregates over multi-tenant entities [SEC-TENANT].
- The absence of HTTPS, HSTS, Secure cookie flags, or a Content Security Policy. The MCP can't see them, so list them under Verify in Environment.

## Finding Gate
Apply this to every candidate finding:
1. **Check the baseline entry.** If the platform control applies and you found no bypass, don't report it. Add it to **Platform Controls Relied On**.
2. **Check visibility.** If the answer depends on a setting the MCP can't see (baseline section 3), don't report it. Add it to **Verify in Environment** with the exact setting.
3. **Require evidence.** A finding needs an observed element and property, such as `getServerAction(CustomLogin)` showing an Aggregate on `AppUser.PasswordHash` followed by `Login`. Never report something only because you didn't find it.
4. **Assign confidence.** **Confirmed** means the evidence shows the issue directly. **Likely** means the pattern is present but context you couldn't see could change it. Anything weaker goes to Verify in Environment, not to the findings.

## Output Format
Start with an `## Audit Context` section listing the items from step 1. Then add `## Findings` and output each finding in the following format:

### [SEC-###] [SEVERITY: Critical/High/Medium/Low] <Finding Title>
- **Vulnerability Category**: (e.g., Broken Object Level Authorization, SQL Injection, Stored XSS)
- **Target Location**: `<Module Name>` -> `<Action / Screen / SQL Node>`
- **Evidence**: The MCP tool call and the elements and properties you observed.
- **Confidence**: Confirmed / Likely
- **Platform control considered**: The baseline entry and why it doesn't prevent this issue, or "None (no platform default)".
- **Exploitation Vector**: How an unauthorized actor or malicious input could compromise the application.
- **Service Studio Remediation**: Concrete configuration changes or defensive logic to implement.

After the findings, add the **Platform Controls Relied On** and **Verify in Environment** sections described in baseline section 8.
