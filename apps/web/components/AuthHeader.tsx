import Link from "next/link";
import { Logo } from "@/components/Logo";

/** Sits on the page's plain background, above the auth-background gradient panel below it - the
 * Logo mark's center dot is filled with the page's own background color, so it only reads
 * correctly here, not directly on the gradient (see Logo's own doc comment). */
export function AuthHeader() {
  return (
    <header className="bg-background">
      <div className="mx-auto max-w-6xl px-6 py-6">
        <Link href="/">
          <Logo />
        </Link>
      </div>
    </header>
  );
}
