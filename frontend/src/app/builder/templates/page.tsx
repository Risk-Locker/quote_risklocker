import { redirect } from "next/navigation";
import type { Route } from "next";

export default async function BuilderTemplatesIndexPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const resolvedParams = await searchParams;
  if (resolvedParams?.tab === "benefits") {
    redirect("/builder/templates/benefit-templates" as Route);
  }
  redirect("/builder/templates/quotation-templates" as Route);
}
