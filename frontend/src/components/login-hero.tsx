"use client";

import dynamic from "next/dynamic";

// Client boundary so the (server) auth layout can embed the WebGL scene without
// SSR (ssr:false is only allowed inside a client component).
const Scene = dynamic(() => import("./login-hero-3d"), { ssr: false });

export function LoginHero() {
  return <Scene />;
}
