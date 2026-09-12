import "./globals.css";
import AuthGate from "../components/AuthGate";

export const metadata = {
  title: "Sales Intelligence",
  description: "Ranked cybersecurity prospects"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><AuthGate>{children}</AuthGate></body></html>;
}
