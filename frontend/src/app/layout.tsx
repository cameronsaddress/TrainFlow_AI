import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google"; // Using Outfit for headings to add flair
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });

export const metadata: Metadata = {
    title: "TrainFlow AI",
    description: "Enterprise AI Training Generator",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" className="dark">
            <body className={`${inter.variable} ${outfit.variable} font-sans bg-background text-foreground flex min-h-screen`}>
                <Sidebar />
                <main className="flex-1 p-8 overflow-y-auto">
                    {children}
                </main>
            </body>
        </html>
    );
}
