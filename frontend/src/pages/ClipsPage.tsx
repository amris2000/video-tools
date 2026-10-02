import { Heading, VStack } from "@chakra-ui/react";
import { useParams } from "react-router-dom";
import { ClipBrowser } from "../components/clips/ClipBrowser";

export function ClipsPage() {
  const { projectId } = useParams();
  return (
    <VStack align="stretch" spacing={6}>
      <Heading size="lg">Clips</Heading>
      {projectId && (
        <ClipBrowser projectId={projectId} mode="view" enableDateFilterInView />
      )}
    </VStack>
  );
}
