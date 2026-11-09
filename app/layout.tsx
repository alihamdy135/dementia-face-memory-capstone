import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Memento | Personal Memory Assistant",
  description: "A private space for familiar faces, relationships, and the moments you share.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" dir="ltr"><body>{children}</body></html>;
}
