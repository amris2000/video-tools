import {
  Box,
  HStack,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useRef, useState, type ReactNode } from "react";

interface VideoPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  videoUrl: string;
  metadata?: ReactNode;
}

export function VideoPreviewModal({
  isOpen,
  onClose,
  title,
  videoUrl,
  metadata,
}: VideoPreviewModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [mediaError, setMediaError] = useState(false);

  function handleClose() {
    const video = videoRef.current;
    video?.pause();
    if (video) video.currentTime = 0;
    onClose();
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      size="6xl"
      isCentered
      scrollBehavior="inside"
    >
      <ModalOverlay />
      <ModalContent
        maxW={{ base: "calc(100vw - 24px)", xl: "1400px" }}
        maxH="calc(100vh - 32px)"
      >
        <ModalHeader pr={12}>{title}</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          <Stack spacing={4}>
            <Box
              bg="black"
              borderRadius="md"
              overflow="hidden"
              display="flex"
              justifyContent="center"
            >
              <video
                key={videoUrl}
                ref={videoRef}
                src={isOpen && videoUrl ? videoUrl : undefined}
                controls
                preload="metadata"
                style={{
                  display: "block",
                  width: "auto",
                  height: "auto",
                  maxWidth: "100%",
                  maxHeight: "calc(100vh - 220px)",
                }}
                onLoadStart={() => setMediaError(false)}
                onError={() => setMediaError(true)}
              />
            </Box>
            {mediaError && (
              <Stack spacing={1}>
                <Text color="red.600">Could not load this video.</Text>
                <Text as="code" fontSize="xs" overflowWrap="anywhere">
                  {videoUrl}
                </Text>
              </Stack>
            )}
            {metadata && (
              <HStack spacing={4} flexWrap="wrap">
                {metadata}
              </HStack>
            )}
          </Stack>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
