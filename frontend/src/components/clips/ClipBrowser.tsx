import { Alert, AlertIcon, Button, HStack, SimpleGrid, Spinner, Text, VStack } from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { getClips, type Clip } from "../../api/clips";
import { ClipCard } from "./ClipCard";

export type ClipBrowserProps = { projectId: string } & (
  | { mode?: "view"; selectedClipPaths?: never; onSelectionChange?: never }
  | {
      mode: "select";
      /** Controlled selection; the consumer owns it and scopes it to projectId. */
      selectedClipPaths: readonly string[];
      onSelectionChange: (paths: string[]) => void;
    }
);

/** Shared catalog, loading states and cards for viewing and picking clips. */
export function ClipBrowser(props: ClipBrowserProps) {
  const { projectId } = props;
  const [result, setResult] = useState<{ projectId: string; clips?: Clip[]; error?: string } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getClips(projectId, controller.signal).then(
      clips => { if (!controller.signal.aborted) setResult({ projectId, clips }); },
      error => {
        if (!controller.signal.aborted) setResult({ projectId, error: error instanceof Error ? error.message : "Could not load clips." });
      },
    );
    return () => controller.abort();
  }, [projectId, attempt]);

  if (!result || result.projectId !== projectId) {
    return <HStack role="status"><Spinner /><Text>Loading clips…</Text></HStack>;
  }
  if (result.error) {
    return <Alert status="error"><AlertIcon />{result.error}<Button ml={4} onClick={() => { setResult(null); setAttempt(value => value + 1); }}>Retry</Button></Alert>;
  }
  const clips = result.clips ?? [];
  if (!clips.length) return <Text>No clips in this project yet.</Text>;
  const selected = new Set(props.mode === "select" ? props.selectedClipPaths : []);
  const visibleSelected = clips.filter(clip => selected.has(clip.path)).length;

  function toggle(path: string) {
    if (props.mode !== "select") return;
    const next = new Set(props.selectedClipPaths);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    props.onSelectionChange([...next]);
  }

  return (
    <VStack align="stretch" spacing={4}>
      <HStack justify="space-between">
        <Text color="gray.600">{clips.length} clips</Text>
        {props.mode === "select" && (
          <HStack>
            <Text role="status">{visibleSelected} selected</Text>
            <Button size="sm" isDisabled={!props.selectedClipPaths.length} onClick={() => props.onSelectionChange([])}>Clear selection</Button>
          </HStack>
        )}
      </HStack>
      <SimpleGrid columns={{ base: 1, md: 2, xl: 3, "2xl": 4 }} spacing={4}>
        {clips.map(clip => <ClipCard key={clip.path} clip={clip} selected={selected.has(clip.path)}
          onToggle={props.mode === "select" ? () => toggle(clip.path) : undefined} />)}
      </SimpleGrid>
    </VStack>
  );
}
