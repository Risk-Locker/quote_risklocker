import { redirect } from "next/navigation";
import type { Route } from "next";

export default function LegacyBenefitsRedirectPage() {
  redirect("/builder/templates/benefit-templates" as Route);
}
