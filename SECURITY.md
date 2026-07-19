# Security Policy

## Supported versions

Threshold is under active MVP development. Security fixes are applied to the current `main` branch. There are no supported stable release branches yet.

## Reporting a vulnerability

Do not open a public issue or discussion for suspected vulnerabilities.

Use GitHub private vulnerability reporting from the repository's **Security → Advisories → Report a vulnerability** page. If that option is unavailable, contact the repository owner through a verified private channel listed on their GitHub profile and ask for an encrypted reporting path. Do not include exploit details in the initial public contact.

Include, where possible:

- the affected commit or version;
- a minimal reproduction;
- security impact and prerequisites;
- whether the issue is already being exploited;
- suggested mitigations, if known.

You should receive an acknowledgement within seven days. Please allow time for validation and a coordinated fix before public disclosure.

## Scope

Reports about the product source, public CI, dependency chain, authentication, authorization, privacy, or data handling are in scope.

Private deployment topology, operator access, and availability of a specific self-hosted instance are handled by that deployment's operator. Do not probe systems you do not own or have explicit permission to test.

## Safe harbor

Good-faith research that avoids privacy violations, destructive actions, persistence, social engineering, denial of service, and unnecessary data access will not be pursued by the project. Stop testing and report immediately if you encounter personal data or gain access beyond what is required to demonstrate the issue.
