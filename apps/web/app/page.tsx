"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { TopNav } from "@/components/TopNav";
import { api, User } from "@/lib/api";
import { useBrdHref } from "@/lib/useBrdHref";

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

function MarketingLanding() {
  // Signed-out visitors can still see the full nav as a preview of the site's structure -
  // clicking any of these already redirects to /sign-in on its own (each page's own 401 check),
  // so nothing extra needs to be done to gate them.
  const brdHref = useBrdHref();

  return (
    <main className="min-h-screen bg-background text-ink">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link href="/">
          <Logo />
        </Link>
        <nav className="flex items-center gap-6 text-sm">
          <Link href="/dashboard" className="text-ink/60 hover:text-ink">
            Projects
          </Link>
          <Link href="/guide" className="text-ink/60 hover:text-ink">
            Guide
          </Link>
          <Link href={brdHref} className="text-ink/60 hover:text-ink">
            BRD generator
          </Link>
          <Link href="/profile" className="text-ink/60 hover:text-ink">
            My Profile
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

      <section className="auth-background relative overflow-hidden">
        {/* Full-bleed to the right edge of the viewport (not the max-w-6xl text column below),
            with a left-edge fade so the photo's own background blends into the hero gradient
            instead of sitting on top of it like a pasted card. Plain <img>, not next/image: this
            deploys through OpenNext to Cloudflare Workers, which doesn't run Next's built-in
            image-optimization API. */}
        <div
          className="pointer-events-none absolute inset-y-0 right-0 hidden w-[52%] lg:block"
          style={{
            maskImage: "linear-gradient(to right, transparent, black 22%)",
            WebkitMaskImage: "linear-gradient(to right, transparent, black 22%)",
          }}
        >
          <img
            src="/hero-photo.jpg"
            alt="A developer at a laptop with a holographic overlay of code and system diagrams"
            width={1400}
            height={874}
            className="h-full w-full object-cover object-left"
          />
        </div>

        <div className="relative mx-auto max-w-6xl px-6 py-24 text-white sm:py-32">
          <div className="flex max-w-xl flex-col items-start gap-6">
            <p className="rounded-full border border-white/20 px-3 py-1 text-xs font-medium text-white/70">
              Agentic SDLC & codebase intelligence
            </p>
            <h1 className="font-serif text-4xl font-semibold leading-tight sm:text-5xl">
              Turn a change request into a grounded, reviewable plan.
            </h1>
            <p className="text-base leading-relaxed text-white/80 sm:text-lg">
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

/** The signed-in landing spot - distinct from the plain "Projects" card grid at /dashboard, this
 * is a quick-action hub so the logo and "Projects" don't just do the same thing twice. */
function AuthenticatedHome() {
  const brdHref = useBrdHref();

  return (
    <main className="min-h-screen bg-background text-ink">
      <div className="mx-auto max-w-5xl px-4 py-12">
        <TopNav />
      </div>

      <section className="auth-background">
        <div className="mx-auto max-w-5xl px-6 py-16 text-white sm:py-20">
          <p className="inline-block rounded-full border border-white/20 px-3 py-1 text-xs font-medium text-white/70">
            Agentic SDLC & codebase intelligence
          </p>
          <h1 className="mt-4 max-w-xl font-serif text-3xl font-semibold leading-tight sm:text-4xl">
            Welcome back. What do you want to do?
          </h1>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <Link
              href="/dashboard?create=1"
              className="rounded-lg border border-white/20 bg-white/5 p-5 hover:bg-white/10"
            >
              <p className="font-medium">+ Create a project</p>
              <p className="mt-1 text-sm text-white/70">Start a new project to upload requirements and code into.</p>
            </Link>
            <Link href={brdHref} className="rounded-lg border border-white/20 bg-white/5 p-5 hover:bg-white/10">
              <p className="font-medium">Generate a BRD</p>
              <p className="mt-1 text-sm text-white/70">Turn plain-language project details into a full BRD.</p>
            </Link>
            <Link href="/dashboard" className="rounded-lg border border-white/20 bg-white/5 p-5 hover:bg-white/10">
              <p className="font-medium">View your projects</p>
              <p className="mt-1 text-sm text-white/70">See every project's status, documents, and analyses.</p>
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}

export default function HomePage() {
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // Any failure (401, or a transient network/cold-start error) is treated as signed-out rather
    // than getting stuck on a blank loading screen.
    api
      .getCurrentUser()
      .then(setUser)
      .catch(() => {})
      .finally(() => setCheckingAuth(false));
  }, []);

  if (checkingAuth) {
    return <main className="min-h-screen bg-background" />;
  }

  return user ? <AuthenticatedHome /> : <MarketingLanding />;
}
