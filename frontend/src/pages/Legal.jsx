import { Link } from 'react-router-dom'

function LegalShell({ title, updated, children }) {
  return (
    <div className="min-h-full bg-white">
      <header className="border-b border-slate-100">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">FL</span>
            <span className="font-bold text-slate-900">FreelanceLeads</span>
          </Link>
          <nav className="flex gap-4 text-sm text-slate-500">
            <Link to="/privacy" className="hover:text-slate-900">Privacy</Link>
            <Link to="/terms" className="hover:text-slate-900">Terms</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-3xl font-bold text-slate-900">{title}</h1>
        <p className="mt-1 text-sm text-slate-400">Last updated: {updated}</p>
        <div className="prose-sm mt-8 space-y-6 text-[15px] leading-relaxed text-slate-600 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-slate-900 [&_li]:ml-5 [&_li]:list-disc">
          {children}
        </div>
      </main>
      <footer className="border-t border-slate-100 py-6 text-center text-sm text-slate-400">
        © {new Date().getFullYear()} FreelanceLeads · <a className="hover:text-slate-600" href="mailto:moinmail001@gmail.com">moinmail001@gmail.com</a>
      </footer>
    </div>
  )
}

export function PrivacyPolicy() {
  return (
    <LegalShell title="Privacy Policy" updated="August 1, 2026">
      <p>
        FreelanceLeads ("we", "us", "the Service"), accessible at https://fl.fewly.tech, is a lead
        generation platform for freelancers and agencies. This policy explains what data we collect,
        how we use it, and the choices you have. By using the Service you agree to this policy.
      </p>

      <h2>1. Information we collect</h2>
      <ul>
        <li><strong>Account data:</strong> your name, email address, and password (stored hashed).</li>
        <li><strong>Usage data:</strong> searches you run, leads you save, pipeline activity, AI generations, and quota counters needed to operate your subscription.</li>
        <li><strong>Business lead data:</strong> publicly available information about businesses (name, address, phone, website, public ratings) gathered from public sources to provide the lead search feature.</li>
        <li><strong>Payment data:</strong> processed by Stripe. We never store your card details; we keep only your Stripe customer reference and invoice status.</li>
      </ul>

      <h2>2. Google user data (Gmail integration)</h2>
      <p>
        If you choose to connect a Gmail account for outreach, we request access to Gmail
        (scope: <code>https://mail.google.com/</code>) strictly to provide features you explicitly
        initiate:
      </p>
      <ul>
        <li><strong>Sending:</strong> we send outreach emails and follow-ups that you compose or approve, from your address, at your direction.</li>
        <li><strong>Reading:</strong> we poll your inbox only to detect replies to messages the Service sent, so that sequences stop automatically and replies appear in your unified inbox. We do not read, index, or store unrelated emails.</li>
      </ul>
      <p>
        OAuth tokens are stored encrypted (AES-128 via Fernet) and are used only to perform the
        actions above. We do not share Google user data with any third party, we do not sell it, we
        do not use it for advertising, and we do not use any Google user data to develop, improve,
        or train generalized artificial intelligence or machine learning models.
      </p>
      <p>
        FreelanceLeads' use and transfer of information received from Google APIs adheres to the{' '}
        <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noreferrer" className="text-indigo-600 underline">
          Google API Services User Data Policy
        </a>, including the Limited Use requirements.
      </p>
      <p>
        You can disconnect your Google account at any time from Outreach → Email Accounts, or by
        revoking access at{' '}
        <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer" className="text-indigo-600 underline">
          myaccount.google.com/permissions
        </a>. Disconnecting deletes our stored tokens.
      </p>

      <h2>3. How we use information</h2>
      <ul>
        <li>To provide, maintain, and improve the Service.</li>
        <li>To generate AI content (pitches, demo sites) you request — inputs are your lead data, never your Gmail content.</li>
        <li>To enforce plan limits and prevent abuse.</li>
        <li>To send transactional messages about your account.</li>
      </ul>

      <h2>4. Sharing</h2>
      <p>
        We do not sell personal data. We share data only with processors required to run the
        Service: Stripe (payments), our hosting provider, an AI inference provider (receives lead
        business data you ask it to write about, never your Gmail data), and email/DNS
        infrastructure needed to verify deliverability. Each processor is bound to use data only to
        provide their service to us.
      </p>

      <h2>5. Data retention & deletion</h2>
      <p>
        Account data is retained while your account is active. You may request deletion of your
        account and all associated data at any time by emailing{' '}
        <a href="mailto:moinmail001@gmail.com" className="text-indigo-600 underline">moinmail001@gmail.com</a> — we
        complete deletion within 30 days. Encrypted email tokens are deleted immediately when you
        disconnect an email account.
      </p>

      <h2>6. Security</h2>
      <p>
        All traffic is encrypted in transit (TLS). Email credentials and OAuth tokens are encrypted
        at rest. Access to production systems is restricted to authorized personnel.
      </p>

      <h2>7. Changes & contact</h2>
      <p>
        We may update this policy; material changes will be announced in-app. Questions:{' '}
        <a href="mailto:moinmail001@gmail.com" className="text-indigo-600 underline">moinmail001@gmail.com</a>.
      </p>
    </LegalShell>
  )
}

export function TermsOfService() {
  return (
    <LegalShell title="Terms of Service" updated="August 1, 2026">
      <p>
        These Terms govern your use of FreelanceLeads at https://fl.fewly.tech. By creating an
        account you agree to them.
      </p>

      <h2>1. The Service</h2>
      <p>
        FreelanceLeads helps freelancers find local business leads, audit their online presence,
        generate AI-assisted outreach content and demo websites, and manage a sales pipeline. Lead
        data is compiled from publicly available sources and provided "as is" without guarantee of
        accuracy.
      </p>

      <h2>2. Your account</h2>
      <ul>
        <li>You must provide accurate information and keep your credentials secure.</li>
        <li>You are responsible for all activity under your account and within your team.</li>
        <li>One person per seat; seat limits depend on your plan.</li>
      </ul>

      <h2>3. Acceptable use</h2>
      <ul>
        <li>You must comply with applicable anti-spam laws (e.g. CAN-SPAM, GDPR, PECR) when sending outreach. You are the sender of record for all emails sent through your connected accounts.</li>
        <li>No unlawful, deceptive, or abusive content; no harassment; no misrepresentation of AI-generated estimates as verified facts.</li>
        <li>No scraping, reselling, or bulk-exporting of the Service's lead database outside the product's export features.</li>
        <li>We may throttle or suspend accounts that endanger deliverability infrastructure or violate these Terms.</li>
      </ul>

      <h2>4. Plans & billing</h2>
      <ul>
        <li>Paid plans are billed monthly via Stripe and renew automatically until cancelled.</li>
        <li>Cancelling stops future charges; access continues until the end of the paid period.</li>
        <li>Quota limits (searches, AI generations, email sends) reset each billing period and unused quota does not roll over except where the product explicitly carries credits over on upgrades.</li>
      </ul>

      <h2>5. AI-generated content</h2>
      <p>
        AI outputs (pitches, proposals, demo sites) are drafts generated from data you provide. You
        are responsible for reviewing them before sending or publishing. Revenue estimates and
        opportunity scores are heuristics, not guarantees.
      </p>

      <h2>6. Intellectual property</h2>
      <p>
        You retain rights to content you create. We retain rights to the Service, its software, and
        branding. You grant us the limited license needed to operate the Service (e.g. hosting your
        demo sites publicly at your direction).
      </p>

      <h2>7. Disclaimers & liability</h2>
      <p>
        The Service is provided "as is" without warranties. To the maximum extent permitted by law,
        our aggregate liability is limited to the amounts you paid in the 3 months preceding the
        claim. We are not liable for indirect or consequential damages, lost profits, or actions
        taken by email providers against accounts you connect.
      </p>

      <h2>8. Termination</h2>
      <p>
        You may close your account at any time. We may suspend or terminate accounts for breach of
        these Terms with notice where practicable.
      </p>

      <h2>9. Changes & contact</h2>
      <p>
        We may update these Terms; continued use after changes constitutes acceptance. Contact:{' '}
        <a href="mailto:moinmail001@gmail.com" className="text-indigo-600 underline">moinmail001@gmail.com</a>.
      </p>
    </LegalShell>
  )
}
