import { redirect } from "next/navigation";

export default async function AdminTemplateBuilderRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/builder/templates/${id}/builder`);
}
