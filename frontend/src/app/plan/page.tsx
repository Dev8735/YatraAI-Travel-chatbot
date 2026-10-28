import { Suspense } from "react";
import { Planner } from "@/components/planner/Planner";
import { Spinner } from "@/components/ui";

export const metadata = { title: "Plan a trip — YatraAI" };

export default function PlanPage() {
  return (
    <Suspense fallback={<div className="p-6"><Spinner /></div>}>
      <Planner />
    </Suspense>
  );
}
