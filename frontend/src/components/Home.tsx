import clsx from "clsx";

import { ChatKitPanel } from "./ChatKitPanel";
import { FactCard } from "./FactCard";
import { ThemeToggle } from "./ThemeToggle";
import { ColorScheme } from "../hooks/useColorScheme";
import { useFacts } from "../hooks/useFacts";

export default function Home({
  scheme,
  handleThemeChange,
}: {
  scheme: ColorScheme;
  handleThemeChange: (scheme: ColorScheme) => void;
}) {
  const { facts, refresh, performAction } = useFacts();

  const containerClass = clsx(
    "min-h-screen bg-gradient-to-br transition-colors duration-300",
    scheme === "dark"
      ? "from-slate-900 via-slate-950 to-slate-850 text-slate-100"
      : "from-slate-100 via-white to-slate-200 text-slate-900"
  );

  return (
    <div className={containerClass}>
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-6 py-8">
        {/* Header Section - Top */}
        <header className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold sm:text-4xl">
                Amazon Seller Assistant
              </h1>
              <p className="max-w-2xl text-sm text-slate-600 dark:text-slate-300">
                Ask questions about Amazon seller policies and procedures.
              </p>
            </div>
            <ThemeToggle value={scheme} onChange={handleThemeChange} />
          </div>
        </header>

        {/* Chat Panel - Below Header */}
        <div className="relative w-full flex h-[calc(100vh-200px)] items-stretch overflow-hidden rounded-3xl bg-white/80 shadow-[0_45px_90px_-45px_rgba(15,23,42,0.6)] ring-1 ring-slate-200/60 backdrop-blur dark:bg-slate-900/70 dark:shadow-[0_45px_90px_-45px_rgba(15,23,42,0.85)] dark:ring-slate-800/60">
          <ChatKitPanel
            theme={scheme}
            onWidgetAction={performAction}
            onResponseEnd={refresh}
            onThemeRequest={handleThemeChange}
          />
        </div>
      </div>
    </div>
  );
}
