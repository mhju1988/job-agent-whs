"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { backgroundThemeFor } from "@/lib/background-theme";

/**
 * Keeps the `<html data-bg="…">` attribute in sync with the current route so
 * the `.animated-bg` blobs recolour per page (see globals.css).
 *
 * Mounted once in the root layout. Reads the path on every navigation and
 * writes the resolved theme key onto `document.documentElement`; removing
 * the attribute on unmount keeps a clean slate. No markup is rendered, so it
 * is safe to mount alongside the server-rendered `<AnimatedBackground />`.
 */
export function BackgroundThemeSync() {
  const pathname = usePathname();
  useEffect(() => {
    const theme = backgroundThemeFor(pathname ?? "/");
    document.documentElement.setAttribute("data-bg", theme);
    return () => {
      document.documentElement.removeAttribute("data-bg");
    };
  }, [pathname]);
  return null;
}
