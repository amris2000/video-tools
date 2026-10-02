import {
  Box,
  HStack,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Tag,
  Text,
  VStack,
} from "@chakra-ui/react";
import { type Clip } from "../../api/clips";

interface ClipJournalModalProps {
  isOpen: boolean;
  onClose: () => void;
  clip: Clip | null;
}

export function ClipJournalModal({
  isOpen,
  onClose,
  clip,
}: ClipJournalModalProps) {
  const journal = clip?.journal;

  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Related journal</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          {!clip || !journal ? (
            <Text color="gray.600">
              No related journal entry found for this clip.
            </Text>
          ) : (
            <VStack align="stretch" spacing={3}>
              <Text fontWeight="semibold">
                {journal.activity || "Untitled activity"}
              </Text>

              <Text color="gray.600">
                {journal.date ?? "Unknown date"}
                {journal.start_time ? ` ${journal.start_time}` : ""}
                {journal.end_time ? `-${journal.end_time}` : ""}
              </Text>

              {journal.location && <Text>Location: {journal.location}</Text>}

              {journal.highlight && <Text>Highlight: {journal.highlight}</Text>}

              {!!journal.tags.length && (
                <Box>
                  <HStack spacing={2} flexWrap="wrap">
                    {journal.tags.map((tag) => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                  </HStack>
                </Box>
              )}
            </VStack>
          )}
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
