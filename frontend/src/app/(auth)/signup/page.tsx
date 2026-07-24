"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { supabase } from "@/lib/supabase";
import { passwordsMatch, isSignupDisabledError, fetchSignupAllowed } from "@/lib/auth-validation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [signupClosed, setSignupClosed] = useState(false);

  useEffect(() => {
    let active = true;
    void fetchSignupAllowed(
      process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
    ).then((allowed) => {
      if (active && !allowed) setSignupClosed(true);
    });
    return () => {
      active = false;
    };
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!passwordsMatch(password, confirmPassword)) {
      toast.error("Passwords don't match.");
      return;
    }
    setLoading(true);
    const { data, error } = await supabase.auth.signUp({ email, password });
    setLoading(false);
    if (error) {
      // The project may have been closed to signups since the page loaded.
      if (isSignupDisabledError(error)) {
        setSignupClosed(true);
        return;
      }
      toast.error(error.message);
      return;
    }
    if (data.session) {
      router.replace("/");
    } else {
      toast.success("Account created — check your email to confirm, then sign in.");
      router.replace("/login");
    }
  }

  if (signupClosed) {
    return (
      <Card className="border-border/80 bg-card/70 p-8">
        <h2 className="font-display text-2xl font-semibold">Access is by demo account</h2>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          This is a university project running on free academic infrastructure, so public sign-ups are
          turned off — every account consumes the shared LLM quota. Ask for a demo account and you&apos;ll
          get one with sample data already loaded.
        </p>
        <Button asChild className="mt-6 w-full">
          <a
            href="https://github.com/mhju1988/job-agent-whs/issues/new?title=Demo%20account%20request"
            target="_blank"
            rel="noopener noreferrer"
          >
            Request a demo account
          </a>
        </Button>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          Prefer to run your own copy? The{" "}
          <a
            href="https://github.com/mhju1988/job-agent-whs#quick-start-with-docker"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-primary hover:underline"
          >
            repo has a two-command Docker setup
          </a>
          .
        </p>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </Card>
    );
  }

  return (
    <Card className="border-border/80 bg-card/70 p-8">
      <h2 className="font-display text-2xl font-semibold">Create your account</h2>
      <p className="mt-1 text-sm text-muted-foreground">Start automating your job hunt.</p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm-password">Confirm password</Label>
          <PasswordInput
            id="confirm-password"
            autoComplete="new-password"
            required
            minLength={6}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Creating…" : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </Card>
  );
}
