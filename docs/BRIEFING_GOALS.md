# AI Briefing: goal ledger

The owner's newsletter goals, with status and evidence. Updated at each milestone.
Status: done (with evidence), in progress, blocked (what is needed).

| # | Goal (owner's words, condensed) | Status | Evidence / what is needed |
|---|---|---|---|
| 1 | Twice-daily plain-English AI + markets newsletter (2026-11-12) | done | `faf673c`..`e81419e`; 91 offline tests pass at `9ddf948` |
| 2 | Formal and careful for Huawei employees; sensitive topics handled (2026-11-20) | done | `d14186a`, `dc07a87`: term and place+word pair checks on drafts; live run rewrote a US-China chip story |
| 3 | Two channels: a few AI stories, a few financial ones (2026-11-20) | done | `d14186a`: AI Channel and Markets Channel per edition |
| 4 | Morning: Greater China, Asia-Pacific, Singapore. Night: US and how China traded that day | done | `dc07a87`: block order per edition in `config/briefing.yaml`, titles and tense from the data |
| 5 | Accuracy: every source fixed, figures double-checked | done | `7b7b781`: Tencent and Sina second source, conflicting figures withheld; live check 2026-11-20 02:15 UTC: S&P 500, Nasdaq, Dow, Nvidia, TSMC confirmed exactly, no conflicts. No second source exists for STI, DBS, SOX, FX, futures (measured stale). Known gap: CSI 300 and Hang Seng TECH (Tencent only) are marked closed while trading, so a late run uses past tense for those two rows |
| 6 | Runs daily on its own (search, check, write, push) Mon-Fri | in progress | code and Task Scheduler slots fixed in `9ddf948`; PowerShell not run here (no pwsh); needs one run on the owner's Windows laptop |
| 7 | Auto-post into the owner's WeLink groups or chats with Playwright | in progress | `src/briefing/welink.py` being rebuilt; real WeLink cannot be reached from the cloud, so first send must be tested on the owner's laptop |
| 8 | Ready to scale to everyone | blocked | email path built and tested offline; no live send yet (needs a Resend key and subscriber list) |
