# Best Self-Hosted GitHub Alternatives in 2026 — Tested and Ranked

GitHub's March 2026 pricing changes introduced costs for self-hosted runner minutes at $0.002/minute, making CI/CD at scale more expensive than it used to be. GitHub Team costs $4/user/month. GitHub Enterprise is $21/user/month. For a 50-person engineering team on Enterprise, that's $12,600/year — before any runner costs, storage overages, or Copilot add-ons.

Beyond cost, three other concerns drive teams toward self-hosted Git hosting. Data sovereignty: your source code lives on Microsoft's infrastructure unless you self-host. AI training concerns: GitHub's terms around Copilot and training data have prompted some organisations to move proprietary code off-platform. And the Atlassian server end-of-life precedent: teams that watched Atlassian kill Jira Server in 2024 are more cautious about platform dependency.

This article covers the strongest self-hosted Git alternatives in 2026 — primarily Gitea and its community fork Forgejo — with setup requirements, feature comparisons, and migration guidance.

---

## 1. The Self-Hosted Git Landscape in 2026

Three tools dominate the self-hosted Git space:

**Forgejo** is a community-governed fork of Gitea that split in late 2022 when Gitea Ltd. became a for-profit entity. By 2026, Forgejo has shipped features faster, has better community governance, and is the default recommendation across most self-hosting communities (r/selfhosted, the Awesome-Selfhosted list, Codeberg). Forgejo is what Codeberg — the largest free-software Git hosting platform — runs.

**Gitea** is the original project, now maintained by Gitea Ltd. The codebase is still 95% identical to Forgejo in 2026. If you're already running Gitea and it works, there's no urgent reason to migrate. If you're choosing today, the community direction favours Forgejo.

**GitLab CE** is the open-source community edition of GitLab. It's significantly more capable than Gitea/Forgejo — full CI/CD with pipelines, a container registry, a package registry, security scanning, and a built-in Kubernetes integration — but it also requires substantially more resources (8GB+ RAM recommended) and more maintenance overhead. GitLab CE is the right choice for teams that need a full DevSecOps platform, not just Git hosting.

This article focuses primarily on Forgejo and Gitea since they cover the use case most teams have: lightweight, self-hosted Git hosting that replaces GitHub's core functionality without the operational complexity of GitLab.

---

## 2. What Forgejo/Gitea Actually Provides

Both tools are written in Go and ship as a single static binary. They run on a Raspberry Pi, a $6/month VPS, or a bare-metal server in a data centre. Resource requirements: 512MB RAM for personal use, 1–2GB for small teams, 4GB for larger teams with active CI.

The feature set covers what most teams actually use GitHub for:

**Repository management:** Full Git hosting with branches, tags, releases, and LFS (Large File Storage). Pull/merge requests with code review, inline comments, approval requirements, and merge protections.

**Issue tracking:** Issues, labels, milestones, and project boards. Not as capable as GitHub Projects' 2026 version, but covers standard issue tracking workflows.

**CI/CD:** Forgejo Actions and Gitea Actions are GitHub Actions-compatible — your existing workflow YAML files run without modification in most cases. This is the single most important feature for teams migrating from GitHub, since it eliminates the CI/CD rewrite that self-hosted Git used to require.

**Package registries:** npm, Maven, PyPI, Docker, Helm, Composer, and RubyGems registries built in. You can host your own packages alongside your code without a separate Artifactory or Nexus instance.

**Authentication:** LDAP, SMTP, OAuth2 (GitHub, Google, GitLab, Microsoft, Discord, generic OIDC), SAML 2.0, and PAM. Enterprise SSO works without add-ons.

**Webhooks and API:** REST API compatible with the Gitea API spec. Webhooks for all major events. Most GitHub-adjacent tooling (Dependabot alternatives, changelog generators, release automations) has community integrations.

---

## 3. Forgejo vs Gitea: Which to Choose

The functional difference in 2026 is small — 95% of the codebase is identical. The differences that exist are:

**Governance:** Forgejo is governed by a non-profit foundation with quarterly contributor meetings and a transparent roadmap. Gitea is governed by Gitea Ltd., a for-profit company registered in Hong Kong. If license stability and community control matter to your organisation, Forgejo's governance model is more aligned with open-source principles.

**Feature velocity:** Forgejo has shipped features faster since the fork — Forgejo Actions reached GitHub Actions compatibility ahead of Gitea Actions. ActivityPub federation (allowing repositories to federate across instances, similar to Mastodon) is a Forgejo-first feature.

**Security defaults:** Forgejo's Actions runner doesn't automatically mount the Docker socket, which is a meaningful security improvement over the default Gitea runner configuration. Forgejo also ships LXC container builds for more secure CI isolation.

**Community direction:** Most "best self-hosted Git" recommendations in 2026 have shifted from Gitea to Forgejo. The Awesome-Selfhosted list, r/selfhosted, and Codeberg all align with Forgejo.

**Migration:** If you're running Gitea now, migration to Forgejo is straightforward — the database formats are compatible. There's no urgency to migrate if Gitea is working, but new deployments should start with Forgejo.

---

## 4. Setting Up Forgejo: What It Actually Takes

The Docker Compose deployment is the standard path. Here's what the process involves.

**Requirements:** A Linux server with 1–2GB RAM (a $6/month VPS handles teams up to 20, $12/month for up to 50), Docker and Docker Compose, a domain, and DNS configured.

**Step 1: Create a Docker Compose file.** The official Forgejo Docker image is at `codeberg.org/forgejo/forgejo`. A minimal `docker-compose.yml` runs Forgejo with a PostgreSQL database.

**Step 2: Configure environment variables.** Set your domain, database credentials, admin email, and SSH port. The configuration is documented and defaults are sensible.

**Step 3: Start the containers.** `docker compose up -d` starts Forgejo and PostgreSQL. The setup wizard runs on first access via your domain.

**Step 4: Configure SSL.** Caddy or Nginx as a reverse proxy handles SSL via Let's Encrypt. The Forgejo documentation covers both setups.

**Step 5: Configure Actions runners.** If you're using Forgejo Actions for CI/CD, register one or more runners against your instance. Runners can run on the same server or on separate machines.

Total time: 1–3 hours for someone comfortable with Docker and Linux. Ongoing maintenance: 1–2 hours per month for updates and backup verification.

---

## 5. Migrating from GitHub to Forgejo

The migration path is well-documented and the tooling has matured significantly.

**Repository migration:** Forgejo has a built-in migration wizard that pulls repositories directly from GitHub, including commit history, issues, pull requests, labels, milestones, and releases. Authentication via a GitHub personal access token is required. The migration runs in the background and handles repositories of any size.

**CI/CD migration:** GitHub Actions workflows are largely compatible with Forgejo Actions. Most standard actions (`actions/checkout`, `actions/setup-python`, `actions/setup-node`) have Forgejo-compatible equivalents maintained by the community. Marketplace actions that have no equivalent need to be rewritten, but the majority of common CI patterns work without modification.

**What doesn't migrate automatically:** GitHub Packages (you'll need to re-push package artifacts to your Forgejo package registry), GitHub Pages (set up a separate static hosting solution or self-host), GitHub Secrets (recreate in Forgejo's secret management), and any GitHub-specific features like Dependabot (use Renovate as a self-hosted alternative).

**Recommended migration approach:** Run Forgejo in parallel with GitHub for 4–6 weeks. Mirror active repositories to Forgejo using the built-in repository mirroring feature — commits to GitHub automatically sync to Forgejo. Migrate CI/CD for one project at a time, verify it works, then cut over. Don't attempt a hard cutover of the entire organisation at once.

---

## 6. Forgejo/Gitea vs GitHub: Honest Comparison

| Factor | GitHub Team | Forgejo (self-hosted) |
|---|---|---|
| Cost (50 people) | $2,400/year | $0 + ~$144/year server |
| GitHub Actions compatible | Native | Forgejo Actions |
| Copilot AI coding | $10–19/user/month add-on | Not included |
| Package registry | Yes | Yes (npm, PyPI, Docker, etc.) |
| Self-hosting | No | Yes |
| Data residency | Microsoft cloud | Your infrastructure |
| Community integrations | Largest ecosystem | Smaller but growing |
| Setup complexity | Zero | 1–3 hours |
| Maintenance overhead | None | 1–2 hrs/month |
| Issue tracking | GitHub Projects (capable) | Basic |
| Security scanning | GitHub Advanced Security (paid) | Requires separate tooling |

The honest gaps: GitHub's issue tracking has improved significantly with GitHub Projects in 2024–2026 and is now more capable than Forgejo's. GitHub Copilot is a genuine productivity tool with no self-hosted equivalent of comparable quality. GitHub's security tooling (Dependabot, secret scanning, code scanning) is more mature and requires additional setup to replicate on self-hosted infrastructure.

---

## 7. Who Should Switch, and Who Should Stay

**Switch to Forgejo/Gitea if:** your team is paying for GitHub Enterprise and the cost is a meaningful budget concern, you have compliance or data sovereignty requirements that require code to stay on your infrastructure, you have the DevOps capacity to manage a self-hosted server, or you're concerned about dependency on Microsoft's platform decisions.

**Stay on GitHub if:** your team benefits significantly from GitHub Copilot and considers it productivity-critical, your open-source projects depend on GitHub's visibility for attracting contributors, your CI/CD relies heavily on GitHub Marketplace actions that have no Forgejo equivalents, or you don't have anyone who can manage self-hosted infrastructure.

The cost calculation is clearest for teams on GitHub Enterprise. A 50-person team saves $12,600/year in licensing by switching to self-hosted Forgejo — enough to pay for a dedicated DevOps hire for a meaningful portion of the year. For teams on GitHub Team at $4/user/month, the cost saving is smaller and the decision depends more on data sovereignty concerns than pure economics.

---

*OSALFinder tracks open-source alternatives to popular SaaS tools. See our [GitHub vs Gitea comparison page](/github-vs-gitea/) for a regularly updated feature and pricing breakdown.*
