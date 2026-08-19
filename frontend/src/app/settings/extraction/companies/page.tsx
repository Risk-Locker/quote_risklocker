import { redirect } from "next/navigation";
import type { Route } from "next";

export default function RedirectPage() {
  redirect("/extraction/company-detection" as Route);
}
