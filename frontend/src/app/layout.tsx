import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import NavLinks from "@/components/NavLinks";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ClearMatch — invoice-to-PO decisions",
  description:
    "Upload a vendor invoice; get an explainable AUTO-APPROVE / NEEDS REVIEW / REJECT decision.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-slate-50 text-slate-900">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/85 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-2.5">
            <Link href="/" className="flex items-baseline gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-blue-600">
              <span className="text-lg font-bold tracking-tight text-blue-700">ClearMatch</span>
              <span className="hidden text-xs text-slate-500 sm:inline">
                invoice-to-PO matching, with reasons
              </span>
            </Link>
            <NavLinks />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
        <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
          ClearMatch · Zamp ASA case study · PS-1: the LLM extracts, the rules decide.
        </footer>
      </body>
    </html>
  );
}
