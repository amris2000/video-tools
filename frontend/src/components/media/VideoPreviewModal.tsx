import {
  AspectRatio,
  HStack,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Stack,
} from "@chakra-ui/react";
import { useEffect, useRef, type ReactNode } from "react";

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

  function resetVideo() {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    video.removeAttribute("src");
    video.load();
  }

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (!isOpen || !videoUrl) {
      resetVideo();
      return;
    }
    video.src = videoUrl;
    video.load();
    return resetVideo;
  }, [isOpen, videoUrl]);

  function handleClose() {
    resetVideo();
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
            <AspectRatio
              ratio={16 / 9}
              bg="black"
              borderRadius="md"
              overflow="hidden"
            >
              <video ref={videoRef} controls preload="metadata" />
            </AspectRatio>
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
