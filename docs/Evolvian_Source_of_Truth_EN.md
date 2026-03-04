# Evolvian Source of Truth (Client-Facing, EN)
Last updated: March 3, 2026

## 1) What this document is
This is the master reference for clients and prospects who want to understand what Evolvian does, how it works, and which plan they need.

Use this as the official, user-friendly source of truth for:
- Product context
- Core functionalities
- Real business use cases
- Plan comparison and limits

## 2) What Evolvian is
Evolvian is an AI operations assistant platform for businesses.

It helps teams deploy AI assistants trained on their own content so they can:
- Answer customer questions faster
- Reduce repetitive support work
- Capture lead and contact data
- Manage appointments and reminders
- Operate across web chat, WhatsApp, and email

In simple terms: Evolvian turns your business knowledge into operational AI support.

## 3) Who Evolvian is for
Evolvian is designed for teams that need practical automation, not just a chatbot demo.

Typical users:
- Small and medium businesses handling frequent customer messages
- Service teams booking appointments
- Operations teams that need consistent responses across channels
- Sales/support teams that want better response speed and better lead handling

## 4) Core functionalities
## 4.1 AI assistant trained on your business
- Upload your knowledge (PDF/TXT and operational context)
- Evolvian indexes your content (RAG-based retrieval)
- Assistant answers using your business information and configured instructions

## 4.2 Website chat widget
- Add a floating chat widget to your website, or embed via iframe
- Configure assistant name, behavior, and key widget settings from dashboard
- Track interactions in chat history

## 4.3 WhatsApp integration
- Connect WhatsApp Business (Meta Cloud API credentials required)
- Receive and answer customer messages with business context
- Use templates for confirmations and reminders (eligible plans)

## 4.4 Email workflows
- Enable email support and automation for follow-up scenarios
- Use templates for appointment confirmations and operational communication
- Available on eligible plans (typically Premium and above)

## 4.5 Appointments and reminders
- Configure scheduling flows
- Confirm appointments automatically
- Send reminders and follow-up messages
- Reduce no-shows and manual coordination

## 4.6 Calendar sync
- Connect Google Calendar
- Show only valid available slots to customers
- Avoid double-booking and schedule conflicts
- Manage booking rules (notice, buffer, slot duration, days ahead)

## 4.7 Dashboard and controls
- Plan and usage visibility (messages/documents)
- Document management
- Assistant prompt configuration
- Session and widget behavior controls
- History view and operational supervision

## 4.8 Privacy, consent, and trust controls
- Client data isolation by account
- Consent controls (terms/privacy/marketing where applicable)
- Legal links in widget experience
- Privacy request workflow support

## 5) How Evolvian works (client journey)
1. Create account and access dashboard.
2. Choose plan (Free, Starter, Premium, or White Label).
3. Upload business documents/context.
4. Configure assistant behavior and widget settings.
5. Install widget (floating script or iframe).
6. Optionally connect channels (WhatsApp, email) and calendar.
7. Go live and monitor usage/history.
8. Optimize prompts, templates, and operational flows over time.

## 6) Widget integration options
## 6.1 Option A: Floating widget (recommended)
Use the installation code generated in your dashboard.

Example:
```html
<script
  type="module"
  src="https://evolvian-assistant.onrender.com/static/embed-floating.js"
  data-public-client-id="YOUR_PUBLIC_CLIENT_ID"
></script>
```

## 6.2 Option B: Embedded iframe
Use this when you want chat inside a fixed section of your site.

Example:
```html
<iframe
  src="https://evolvian-assistant.onrender.com/static/widget.html?public_client_id=YOUR_PUBLIC_CLIENT_ID"
  style="width:360px;height:520px;border:none;border-radius:12px;"
  allow="clipboard-write; microphone"
  title="Evolvian AI Chat Widget"
></iframe>
```

## 6.3 Basic validation checklist
- Widget appears after page load
- Chat opens correctly
- Assistant responds with your configured context
- Conversation appears in dashboard history

## 7) Plans (current commercial structure)
Important: Final plan details are controlled in-app and may include account-level feature flags.

| Plan | Price | Messages/month | Documents | Main included capabilities |
|---|---|---:|---:|---|
| Free | $0 USD/mo | 100 | 1 | Basic dashboard, web chat widget integration |
| Starter | $19 USD/mo | 1,000 | 1 | Everything in Free + WhatsApp AI setup support |
| Premium | $49 USD/mo | 5,000 | 3 | Everything in Starter + advanced widget customization + custom prompt + WhatsApp appointments/reminders |
| White Label (Enterprise) | Custom | Unlimited | Unlimited | Dedicated onboarding, priority support, enterprise-grade rollout |

### Plan notes
- Start on Free and upgrade later.
- Some advanced channels/features can require both the right plan and channel setup (for example, WhatsApp Business credentials).
- Email automation and advanced operational modules are typically Premium+.

## 8) Real use cases
## 8.1 Customer support
- Answer repetitive questions 24/7 from website and messaging channels
- Reduce ticket volume for common inquiries

## 8.2 Appointment-heavy businesses
- Handle booking flow and confirmations automatically
- Send reminders to reduce no-shows

## 8.3 Lead capture and qualification
- Capture name, email, phone, and use-case details
- Route qualified opportunities faster

## 8.4 Internal knowledge assistant
- Give team members faster access to procedures and FAQs
- Keep answer quality consistent across staff

## 8.5 Industry examples
- Restaurants: menu, hours, reservations
- Clinics/services: appointment scheduling and reminders
- Retail: policies, hours, product/service FAQs
- Technical products: user manual and support workflows

## 9) Security and privacy summary
- Account-level data isolation
- Documents are stored securely
- Uploaded documents are not shared with third parties for external model training
- Controlled access for support/troubleshooting/legal compliance only
- Consent and legal controls available in public and widget experiences

## 10) Product boundaries (important)
To keep expectations clear:
- Assistant quality depends on the quality and completeness of uploaded content
- Channel features can depend on setup status (e.g., WhatsApp Business, Google Calendar, email integration)
- Some features are plan-dependent and may require upgrade

## 11) FAQ (client-facing)
### Can I start for free and upgrade later?
Yes. Most teams start on Free and upgrade as message volume and automation needs increase.

### Which file types can I upload?
PDF and TXT are supported in the standard flow.

### Can Evolvian work in English and Spanish?
Yes. Bilingual operation is supported in common client flows.

### Do I need a developer to launch?
Usually minimal technical help is needed. Most teams can launch quickly using dashboard setup and widget install instructions.

### Is my data used to train external models?
No. Uploaded documents are not shared with third parties for external model training.

### How fast can I launch?
Many teams can go live in less than one day after uploading core knowledge and installing the widget.

## 12) Support and contact
- Main support: support@evolvianai.com
- Privacy requests: privacy@evolvianai.com
- Dashboard/login: https://www.evolvianai.net

---

If you are using this document as an AI knowledge base, keep this file updated whenever plans, limits, or channel capabilities change.
