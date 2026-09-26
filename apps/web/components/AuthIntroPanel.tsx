const FEATURES = [
  "Upload requirement docs and your real codebase - the agent grounds every answer in what you gave it.",
  "Describe a change in plain language and get a full plan: affected files, tasks, test cases, and cited evidence.",
  "Nothing ships on its own - a reviewer approves, edits, or rejects every generated plan before it's final.",
];

export function AuthIntroPanel() {
  return (
    <div className="flex flex-col justify-center gap-8 px-8 py-16 text-white lg:w-1/2 lg:px-16">
      <div>
        <p className="font-serif text-3xl font-semibold">Spectrace AI</p>
        <p className="mt-2 text-sm text-white/70">Agentic SDLC & codebase intelligence platform</p>
      </div>
      <p className="max-w-md text-sm leading-relaxed text-white/80">
        Turn a change request into a grounded, reviewable implementation plan - built from your own
        requirements and code, never invented.
      </p>
      <ul className="flex max-w-md flex-col gap-4">
        {FEATURES.map((feature) => (
          <li key={feature} className="flex gap-3 text-sm leading-relaxed text-white/80">
            <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-trace" />
            {feature}
          </li>
        ))}
      </ul>
    </div>
  );
}
