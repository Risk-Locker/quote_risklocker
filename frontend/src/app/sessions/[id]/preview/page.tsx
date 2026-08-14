import { redirect } from "next/navigation";

export default async function PreviewRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/sessions/${id}?step=preview`);
}
