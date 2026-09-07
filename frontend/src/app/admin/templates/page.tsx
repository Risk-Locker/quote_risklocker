import { redirect } from "next/navigation";
import type { Route } from "next";

export default function AdminTemplatesRedirect() {
  redirect("/builder/templates/quotation-templates" as Route);
}
