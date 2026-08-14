import { redirect } from "next/navigation";

export default function LegacyCompaniesRedirect() {
  // RL-DISABLED legacy-company-builder — disabled 2026-08-14; restore only
  // as a compatibility route, never as a separate Builder destination.
  redirect("/builder/benefits");
}
