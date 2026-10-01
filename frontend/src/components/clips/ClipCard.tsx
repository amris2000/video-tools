import {
  AspectRatio,
  Box,
  Button,
  Checkbox,
  Image,
  Text,
  VStack,
} from "@chakra-ui/react";
import { type Clip } from "../../api/clips";

interface ClipCardProps {
  clip: Clip;
  selected?: boolean;
  onToggle?: () => void;
  compact?: boolean;
  onPreview?: () => void;
}

export function ClipCard({
  clip,
  selected = false,
  onToggle,
  compact = false,
  onPreview,
}: ClipCardProps) {
  const duration =
    clip.duration === null
      ? null
      : Math.floor(clip.duration / 60) +
        ":" +
        String(Math.floor(clip.duration % 60)).padStart(2, "0");
  const technicalMetadata = [
    clip.width && clip.height ? clip.width + " × " + clip.height : null,
    clip.fps ? clip.fps + " fps" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const content = (
    <>
      <AspectRatio ratio={16 / 9} bg="gray.100">
        {clip.thumbnail_url ? (
          <Image
            src={clip.thumbnail_url}
            alt=""
            loading="lazy"
            objectFit="cover"
            fallback={
              <Text color="gray.500" fontSize="xs">
                No thumbnail
              </Text>
            }
          />
        ) : (
          <Text color="gray.500" fontSize="xs">
            No thumbnail
          </Text>
        )}
      </AspectRatio>
      <VStack align="stretch" p={compact ? 2 : 3} spacing={compact ? 1 : 2}>
        {onToggle ? (
          <Checkbox
            isChecked={selected}
            onChange={onToggle}
            colorScheme="blue"
            size={compact ? "sm" : "md"}
          >
            <Text
              fontSize={compact ? "sm" : "md"}
              fontWeight="semibold"
              overflowWrap="anywhere"
            >
              {clip.name}
            </Text>
          </Checkbox>
        ) : (
          <Text
            fontSize={compact ? "sm" : "md"}
            fontWeight="semibold"
            overflowWrap="anywhere"
          >
            {clip.name}
          </Text>
        )}
        {duration && (
          <Text fontSize={compact ? "xs" : "sm"} color="gray.600">
            {duration}
          </Text>
        )}
        {technicalMetadata && (
          <Text fontSize="xs" color="gray.500">
            {technicalMetadata}
          </Text>
        )}
        {!compact && (
          <>
            <Text fontSize="xs" color="gray.500" overflowWrap="anywhere">
              {clip.path}
            </Text>
            {clip.creation_time && (
              <Text fontSize="xs" color="gray.600">
                {clip.creation_time.replace("T", " ")}
              </Text>
            )}
          </>
        )}
        {!duration && !technicalMetadata && (
          <Text fontSize="xs" color="gray.500">
            Metadata unavailable
          </Text>
        )}
      </VStack>
    </>
  );

  if (onPreview) {
    return (
      <Button
        type="button"
        display="block"
        width="100%"
        height="auto"
        p={0}
        whiteSpace="normal"
        textAlign="left"
        bg="white"
        borderWidth="1px"
        borderColor="gray.200"
        borderRadius="md"
        overflow="hidden"
        onClick={onPreview}
        _hover={{ borderColor: "blue.400", transform: "translateY(-1px)" }}
        _active={{ transform: "none" }}
      >
        {content}
      </Button>
    );
  }

  return (
    <Box
      as="article"
      bg="white"
      borderWidth="2px"
      borderColor={selected ? "blue.500" : "gray.200"}
      borderRadius="md"
      overflow="hidden"
    >
      {content}
    </Box>
  );
}
