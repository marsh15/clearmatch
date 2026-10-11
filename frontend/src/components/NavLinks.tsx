"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { apiBase } from "@/lib/api";

export default function NavLinks() {
  const pathname = usePathname();
  const [healthHref, setHealthHref] = useState("/api-base");

  useEffect(() => {
    apiBase().then((base) => setHealthHref(`${base}/api/health`));
  }, []);

  const link = (href: string, label: string) => {
    const active = pathname === href;
    return (
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className={`flex min-h-10 items-center rounded-md px-3 text-sm font-medium transition-colors duration-150
          ${active ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"}`}
      >
        {label}
      </Link>
    );
  };
  return (
    <nav className="flex items-center gap-1" aria-label="Main">
      {link("/", "Run")}
      {link("/dashboard", "Dashboard")}
      <a
        href={healthHref}
        className="ml-2 hidden min-h-10 items-center rounded-md bg-blue-700 px-3 text-sm font-medium text-white transition-colors duration-150 hover:bg-blue-800 sm:flex"
      >
        API health
      </a>
    </nav>
  );
}
