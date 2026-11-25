import { redirect } from "next/navigation";

export default async function SandboxReviewRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/sessions/sandbox/${id}`);
}
