import Link from "next/link";

const FEATURES = [
  {
    title: "Grounded evidence",
    body: "Every claim is traced back to a real chunk of your uploaded requirements or code - never invented.",
  },
  {
    title: "A full implementation plan",
    body: "User story, acceptance criteria, affected files, tasks, and test cases, generated from a plain-language request.",
  },
  {
    title: "Human-gated approval",
    body: "Nothing becomes the plan of record on its own - a reviewer approves, edits, or rejects every version.",
  },
];

const STEPS = [
  {
    label: "01",
    title: "Upload",
    body: "Add your requirement docs and your real codebase - a folder, a ZIP, or a public GitHub repo.",
  },
  {
    label: "02",
    title: "Describe",
    body: "Write the change you want in plain language, the way you'd explain it to a teammate.",
  },
  {
    label: "03",
    title: "Review",
    body: "Get a grounded plan citing exactly where the evidence came from, then approve, edit, or send it back.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-background text-ink">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <span className="font-serif text-lg font-semibold">Spectrace AI</span>
        <nav className="flex items-center gap-6 text-sm">
          <Link href="/guide" className="text-ink/60 hover:text-ink">
            How it works
          </Link>
          <Link href="/sign-in" className="text-ink/60 hover:text-ink">
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-md bg-accent px-4 py-2 font-medium text-white hover:opacity-90"
          >
            Get started free
          </Link>
        </nav>
      </header>

      <section className="auth-background">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 px-6 py-24 text-white sm:py-32">
          <p className="rounded-full border border-white/20 px-3 py-1 text-xs font-medium text-white/70">
            Agentic SDLC & codebase intelligence
          </p>
          <h1 className="max-w-3xl font-serif text-4xl font-semibold leading-tight sm:text-6xl">
            Turn a change request into a grounded, reviewable plan.
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-white/80 sm:text-lg">
            Upload your requirements and your real codebase. Describe what needs to change in plain
            language. Spectrace AI finds the evidence, cites it, and proposes exactly which files
            need work - nothing ships until a reviewer says so.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              href="/register"
              className="rounded-md bg-white px-6 py-3 text-sm font-semibold text-accent hover:bg-white/90"
            >
              Get started free
            </Link>
            <Link
              href="/sign-in"
              className="rounded-md border border-white/30 px-6 py-3 text-sm font-semibold text-white hover:bg-white/10"
            >
              Sign in
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="font-serif text-2xl font-semibold sm:text-3xl">
          Built to be trusted, not just fast.
        </h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="rounded-lg border border-ink/10 bg-surface p-6">
              <div className="mb-3 h-1.5 w-8 rounded-full bg-trace" />
              <h3 className="font-medium text-ink">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink/70">{feature.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-ink/10 bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="font-serif text-2xl font-semibold sm:text-3xl">How it works</h2>
          <div className="mt-10 grid gap-8 sm:grid-cols-3">
            {STEPS.map((step) => (
              <div key={step.label}>
                <span className="font-serif text-3xl font-semibold text-trace">{step.label}</span>
                <h3 className="mt-2 font-medium text-ink">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink/70">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="auth-background">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-5 px-6 py-16 text-white">
          <h2 className="font-serif text-2xl font-semibold sm:text-3xl">
            Ready to see it work on your own codebase?
          </h2>
          <Link
            href="/register"
            className="rounded-md bg-white px-6 py-3 text-sm font-semibold text-accent hover:bg-white/90"
          >
            Get started free
          </Link>
        </div>
      </section>

      <footer className="mx-auto max-w-6xl px-6 py-8 text-xs text-ink/50">
        Spectrace AI - agentic SDLC and codebase intelligence platform.
      </footer>
    </main>
  );
}
