import { Button, Heading, HStack, Text, VStack } from "@chakra-ui/react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { ClipBrowser } from "../components/clips/ClipBrowser";

/** Development-only consumer demonstrating mode changes without a new browser. */
export function ClipBrowserDemo() {
  const { projectId } = useParams();
  return projectId ? <Demo key={projectId} projectId={projectId} /> : null;
}

function Demo({ projectId }: { projectId: string }) {
  const [selecting, setSelecting] = useState(false);
  const [paths, setPaths] = useState<string[]>([]);
  return (
    <VStack align="stretch" spacing={6}>
      <Heading size="lg">Clip browser demo</Heading>
      <HStack>
        <Button onClick={() => setSelecting(value => !value)}>
          {selecting ? "View clips" : "Select clips"}
        </Button>
        <Text>Consumer selection: {paths.length} clips</Text>
      </HStack>
      <ClipBrowser projectId={projectId} {...(selecting
        ? { mode: "select" as const, selectedClipPaths: paths, onSelectionChange: setPaths }
        : { mode: "view" as const })} />
      {paths.length > 0 && <Text fontSize="sm" overflowWrap="anywhere">{paths.join(", ")}</Text>}
    </VStack>
  );
}
