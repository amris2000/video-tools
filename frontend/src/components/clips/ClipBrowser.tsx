import {
  Alert,
  AlertIcon,
  AspectRatio,
  Button,
  HStack,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  SimpleGrid,
  Spinner,
  Stack,
  Text,
  VStack,
  useDisclosure,
} from "@chakra-ui/react";
import { useEffect, useRef, useState } from "react";
import { getClips, type Clip } from "../../api/clips";
import { getMediaUrl } from "../../api/workflows";
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
  const [result, setResult] = useState<{
    projectId: string;
    clips?: Clip[];
    error?: string;
  } | null>(null);
  const [previewClip, setPreviewClip] = useState<Clip | null>(null);
  const [attempt, setAttempt] = useState(0);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const previewVideoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    getClips(projectId, controller.signal).then(
      (clips) => {
        if (!controller.signal.aborted) setResult({ projectId, clips });
      },
      (error) => {
        if (!controller.signal.aborted)
          setResult({
            projectId,
            error:
              error instanceof Error ? error.message : "Could not load clips.",
          });
      },
    );
    return () => controller.abort();
  }, [projectId, attempt]);

  if (!result || result.projectId !== projectId) {
    return (
      <HStack role="status">
        <Spinner />
        <Text>Loading clips…</Text>
      </HStack>
    );
  }
  if (result.error) {
    return (
      <Alert status="error">
        <AlertIcon />
        {result.error}
        <Button
          ml={4}
          onClick={() => {
            setResult(null);
            setAttempt((value) => value + 1);
          }}
        >
          Retry
        </Button>
      </Alert>
    );
  }
  const clips = result.clips ?? [];
  if (!clips.length) return <Text>No clips in this project yet.</Text>;
  const selected = new Set(
    props.mode === "select" ? props.selectedClipPaths : [],
  );
  const visibleSelected = clips.filter((clip) =>
    selected.has(clip.path),
  ).length;
  const isViewMode = props.mode !== "select";

  function openPreview(clip: Clip) {
    setPreviewClip(clip);
    onOpen();
  }

  function closePreview() {
    previewVideoRef.current?.pause();
    previewVideoRef.current?.removeAttribute("src");
    previewVideoRef.current?.load();
    setPreviewClip(null);
    onClose();
  }

  function toggle(path: string) {
    if (props.mode !== "select") return;
    const next = new Set(props.selectedClipPaths);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    props.onSelectionChange([...next]);
  }

  return (
    <VStack align="stretch" spacing={isViewMode ? 2 : 4}>
      <HStack justify="space-between">
        <Text color="gray.600">{clips.length} clips</Text>
        {props.mode === "select" && (
          <HStack>
            <Text role="status">{visibleSelected} selected</Text>
            <Button
              size="sm"
              isDisabled={!props.selectedClipPaths.length}
              onClick={() => props.onSelectionChange([])}
            >
              Clear selection
            </Button>
          </HStack>
        )}
      </HStack>
      <SimpleGrid
        columns={
          isViewMode
            ? { base: 2, sm: 3, md: 4, lg: 5, xl: 6 }
            : { base: 1, md: 2, xl: 3, "2xl": 4 }
        }
        spacing={isViewMode ? 2 : 4}
      >
        {clips.map((clip) => (
          <ClipCard
            key={clip.path}
            clip={clip}
            compact={isViewMode}
            selected={selected.has(clip.path)}
            onPreview={isViewMode ? () => openPreview(clip) : undefined}
            onToggle={
              props.mode === "select" ? () => toggle(clip.path) : undefined
            }
          />
        ))}
      </SimpleGrid>
      <Modal
        isOpen={isOpen}
        onClose={closePreview}
        size="6xl"
        isCentered
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent
          maxW={{ base: "calc(100vw - 24px)", xl: "1400px" }}
          maxH="calc(100vh - 32px)"
        >
          <ModalHeader pr={12}>{previewClip?.name}</ModalHeader>
          <ModalCloseButton />
          <ModalBody pb={6}>
            {previewClip && (
              <Stack spacing={4}>
                <AspectRatio
                  ratio={16 / 9}
                  bg="black"
                  borderRadius="md"
                  overflow="hidden"
                >
                  <video
                    ref={previewVideoRef}
                    controls
                    preload="metadata"
                    src={getMediaUrl(projectId, previewClip.path)}
                  />
                </AspectRatio>
                <HStack spacing={4} flexWrap="wrap">
                  <Text fontWeight="semibold">
                    {previewClip.duration === null
                      ? "Duration unavailable"
                      : `${Math.floor(previewClip.duration / 60)}:${String(Math.floor(previewClip.duration % 60)).padStart(2, "0")}`}
                  </Text>
                  {previewClip.width && previewClip.height && (
                    <Text color="gray.600">
                      {previewClip.width} × {previewClip.height}
                    </Text>
                  )}
                  {previewClip.fps && (
                    <Text color="gray.600">{previewClip.fps} fps</Text>
                  )}
                  {previewClip.creation_time && (
                    <Text color="gray.600">
                      {previewClip.creation_time.replace("T", " ")}
                    </Text>
                  )}
                </HStack>
                <Text fontSize="sm" color="gray.500" overflowWrap="anywhere">
                  {previewClip.path}
                </Text>
              </Stack>
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </VStack>
  );
}
