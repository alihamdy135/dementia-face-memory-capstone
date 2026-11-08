import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ذاكرة | مساعد التذكّر",
  description: "مساعد محلي للتعرّف على الوجوه وحفظ الملاحظات بإذن المستخدم.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ar" dir="rtl"><body>{children}</body></html>;
}
