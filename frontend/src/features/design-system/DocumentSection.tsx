import { useState } from "react";

import { ActivityTimeline, type ActivityEvent } from "@/components/ui/ActivityTimeline";
import { DiffViewer } from "@/components/ui/DiffViewer";
import { type DropzoneItem, FileDropzone } from "@/components/ui/FileDropzone";

import { Section, SubHeading, ThemePair } from "./showcase";

const NOW = new Date("2026-10-20T12:00:00Z");
const EVENTS: ActivityEvent[] = [
  { id: 1, actor: "Rita Requester", action: "submitted the request", at: "2026-10-18T09:30:00Z" },
  {
    id: 2,
    actor: "Alex Approver",
    action: "asked for changes",
    at: "2026-10-19T14:10:00Z",
    comment: "Please split the freight cost.",
  },
  { id: 3, actor: "Rita Requester", action: "resubmitted", at: "2026-10-20T08:45:00Z" },
];

const STATIC_ITEMS: DropzoneItem[] = [
  { id: "1", name: "quote-acme.pdf", size: 482_000, status: "uploading", progress: 62 },
  { id: "2", name: "contract.pdf", size: 1_900_000, status: "done" },
  { id: "3", name: "scan.tiff", size: 8_400_000, status: "error", error: "Virus check failed" },
];

function Timeline() {
  const [events, setEvents] = useState(EVENTS);
  const add = (text: string) =>
    setEvents((current) => [
      ...current,
      { id: current.length + 1, actor: "You", action: "added a comment", at: new Date().toISOString(), comment: text },
    ]);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <SubHeading>With comment composer</SubHeading>
        <ActivityTimeline events={events} now={NOW} onAddComment={add} />
      </div>
      <div>
        <SubHeading>Empty</SubHeading>
        <ActivityTimeline events={[]} />
      </div>
    </div>
  );
}

function Dropzones() {
  const [items, setItems] = useState<DropzoneItem[]>([]);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <SubHeading>Try a .exe or a file over 2 MB</SubHeading>
        <FileDropzone
          accept={[".pdf", ".png", "image/jpeg"]}
          maxSizeBytes={2 * 1024 * 1024}
          items={items}
          onRemove={(id) => setItems((current) => current.filter((item) => item.id !== id))}
          onFilesAccepted={(files) =>
            setItems((current) => [
              ...current,
              ...files.map((file, index) => ({
                id: `${file.name}-${current.length + index}`,
                name: file.name,
                size: file.size,
                status: "done" as const,
              })),
            ])
          }
        />
      </div>
      <div className="space-y-4">
        <div>
          <SubHeading>Upload states</SubHeading>
          <FileDropzone onFilesAccepted={() => undefined} items={STATIC_ITEMS} onRemove={() => undefined} />
        </div>
        <div>
          <SubHeading>Disabled</SubHeading>
          <FileDropzone onFilesAccepted={() => undefined} disabled />
        </div>
      </div>
    </div>
  );
}

export function DocumentSection() {
  return (
    <Section
      id="documents"
      title="Timeline, diff and file upload"
      intro="Diffs mark added and removed content with + and − and a spoken word. The dropzone is a real file input, so click, Enter and Space open the picker; dropped files go through the same type and size checks."
    >
      <ThemePair>
        <div className="space-y-8">
          <Timeline />
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <SubHeading>Field changes</SubHeading>
              <DiffViewer
                changes={[
                  { field: "Payment terms", before: "Net 30", after: "Net 45" },
                  { field: "Contact email", before: "ap@acme.test", after: "billing@acme.test" },
                  { field: "Tax ID", before: null, after: "DE811234567" },
                ]}
              />
            </div>
            <div>
              <SubHeading>Text changes</SubHeading>
              <DiffViewer
                before={"Deliver to dock 2\nCall 30 minutes ahead\nNo weekend delivery"}
                after={"Deliver to dock 4\nCall 30 minutes ahead\nNo weekend delivery\nSignature required"}
              />
            </div>
          </div>
          <Dropzones />
        </div>
      </ThemePair>
    </Section>
  );
}
