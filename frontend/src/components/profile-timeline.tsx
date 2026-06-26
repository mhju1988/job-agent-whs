import { Briefcase, GraduationCap } from "lucide-react";
import { formatDateRange } from "@/lib/profile-format";
import type { ProfileEducation, ProfileExperience } from "@/lib/types";

function TimelineItem({
  primary,
  secondary,
  range,
  description,
  last,
}: {
  primary: string;
  secondary: string;
  range: string;
  description?: string | null;
  last: boolean;
}) {
  return (
    <li className="relative pl-6">
      {/* node + connecting line */}
      <span className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-primary bg-background" />
      {!last && (
        <span className="absolute left-[5px] top-4 h-[calc(100%-0.5rem)] w-px bg-border" />
      )}
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="font-medium">{primary}</span>
        {range && (
          <span className="font-mono text-xs text-muted-foreground">{range}</span>
        )}
      </div>
      <div className="text-sm text-muted-foreground">{secondary}</div>
      {description && (
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground/90">
          {description}
        </p>
      )}
    </li>
  );
}

/** Renders CV experience and education as a compact vertical timeline. */
export function ProfileTimeline({
  experience,
  education,
}: {
  experience: ProfileExperience[];
  education: ProfileEducation[];
}) {
  if (experience.length === 0 && education.length === 0) return null;

  return (
    <div className="space-y-6">
      {experience.length > 0 && (
        <div>
          <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
            <Briefcase className="h-3.5 w-3.5" />
            Experience
          </div>
          <ol className="space-y-4">
            {experience.map((exp, i) => (
              <TimelineItem
                key={`${exp.title}-${exp.company}-${i}`}
                primary={exp.title}
                secondary={exp.company}
                range={formatDateRange(exp.start, exp.end)}
                description={exp.description}
                last={i === experience.length - 1}
              />
            ))}
          </ol>
        </div>
      )}

      {education.length > 0 && (
        <div>
          <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
            <GraduationCap className="h-3.5 w-3.5" />
            Education
          </div>
          <ol className="space-y-4">
            {education.map((edu, i) => (
              <TimelineItem
                key={`${edu.degree}-${edu.institution}-${i}`}
                primary={edu.field ? `${edu.degree} · ${edu.field}` : edu.degree}
                secondary={edu.institution}
                range={formatDateRange(edu.start, edu.end)}
                description={edu.description}
                last={i === education.length - 1}
              />
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
