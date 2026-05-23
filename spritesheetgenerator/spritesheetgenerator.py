import krita
import math
import json
from pathlib import Path
from collections import namedtuple
from PyQt5.QtCore import QUuid

class SpritesheetGenerator():

    def __init__(self):
        pass

    def configure(self, exportFilePath, spritesheetType, autoCalculateSize, customRowCount, customColumnCount, ignoreEmptyFrames, targetSpriteWidth, targetSpriteHeight, spritePadding, filterStrategy, layerExclusions):
        self.exportFilePath = exportFilePath
        self.spritesheetType = spritesheetType
        self.autoCalculateSize = autoCalculateSize
        self.customRowCount = max(customRowCount, 1)
        self.customColumnCount = max(customColumnCount, 1)
        self.ignoreEmptyFrames = ignoreEmptyFrames
        self.targetSpriteWidth = targetSpriteWidth
        self.targetSpriteHeight = targetSpriteHeight
        self.spritePadding = spritePadding
        self.finalSpriteWidth = self.targetSpriteWidth + (self.spritePadding * 2)
        self.finalSpriteHeight = self.targetSpriteHeight + (self.spritePadding * 2)
        self.filterStrategy = filterStrategy
        self.layerExclusions = layerExclusions
        self.krita = krita.Krita.instance()
        self.activeDocument = self.krita.activeDocument()
        self.animationStartTime = self.activeDocument.fullClipRangeStartTime()
        self.animationEndTime = self.activeDocument.fullClipRangeEndTime()
        self.frameDuration = self.activeDocument.framesPerSecond()
        self.exportedFrameTimes = []
        # Parallel list to exportedFrameTimes: the animation name each frame belongs to
        self.exportedFrameAnimations = []
        # Parallel list: the marker range end for each exported frame's animation,
        # used to correctly calculate the last keyframe's hold duration
        self.exportedAnimationRangeEnds = []

        print("Spritesheet generator configuration completed")
        print(f"Export file path: {self.exportFilePath}")
        print(f"Spritesheet type: {self.spritesheetType}")
        print(f"Ignore empty frames: {self.ignoreEmptyFrames}")
        print(f"Target width: {self.targetSpriteWidth}")
        print(f"Target height: {self.targetSpriteHeight}")
        print(f"Filter type: {self.filterStrategy}")
        print(f"Animation start time: {self.animationStartTime}")
        print(f"Animation end time: {self.animationEndTime}")

    def export(self):
        # Create a temporary duplicate of the currently active document.
        # All transformations (such as resizing) will be done on this temporary document.
        self._createTemporaryDocument()

        if self._isSpriteResizeRequired():
            print("Sprites will be resized...")
            self._resizeSprites()

        if self.spritePadding > 0:
            print("Adding padding to spritesheet frames...")
            self._applyPaddingToSprites()
        
        self._createSpritesheetDocumentFromFrames()
        self._positionFramesInSpritesheetDocument()
        self._forceCloseDocument(self.temporaryDocument)
        self._exportToFile()
        self._exportMetadata()
        self._forceCloseDocument(self.spritesheetDocument)
        
    def _createTemporaryDocument(self):
        self.temporaryDocument = self.activeDocument.clone()
        self.temporaryDocument.setBatchmode(True)
        
        print("Temporary document created")

    def _isSpriteResizeRequired(self):
        return self.temporaryDocument.width() != self.targetSpriteWidth or self.temporaryDocument.height() != self.targetSpriteHeight
    
    def _resizeSprites(self):
        self.temporaryDocument.scaleImage(self.targetSpriteWidth, self.targetSpriteHeight, self.targetSpriteWidth, self.targetSpriteHeight, self.filterStrategy)
        self.temporaryDocument.refreshProjection()

        print(f"Sprites resized to {self.temporaryDocument.width()} x {self.temporaryDocument.height()}")

    def _applyPaddingToSprites(self):
        # Remove excess pixels that are beyond the bounds of the visible portion of the document.
        self.temporaryDocument.crop(0, 0, self.temporaryDocument.width(), self.temporaryDocument.height())

        # Adjust document offset and size to apply padding.
        self.temporaryDocument.setXOffset(-self.spritePadding)
        self.temporaryDocument.setYOffset(-self.spritePadding)
        self.temporaryDocument.setWidth(self.temporaryDocument.width() + (self.spritePadding * 2))
        self.temporaryDocument.setHeight(self.temporaryDocument.height() + (self.spritePadding * 2))
        self.temporaryDocument.refreshProjection()

        print(f"Padding applied. New document size is {self.temporaryDocument.width()} x {self.temporaryDocument.height()}")

    def _applyLayerExclusion(self, layers):
        print(f"Applying layer exclusions: {str(self.layerExclusions)}")

        for layer in layers:
            id = layer.uniqueId().toString(QUuid.WithoutBraces)
            if id in self.layerExclusions:
                print(f"Layer [{layer.name()} | {id}] will be excluded from the spritesheet")
                layer.setVisible(False)

        print("Finished applying layer exclusions")


    # Pattern for animation marker groups: "A_animname:start-end"
    # e.g. "A_walk:9-16" or "A_walk_cycle:9-16"
    ANIM_MARKER_PREFIX = "A_"
    ANIM_MARKER_PATTERN = r"^A_([^:]+):(\d+)-(\d+)$"

    def _parseAnimationMarkers(self, nodes):
        """
        Scan top-level nodes for animation marker groups matching "A_name:start-end".
        Returns a list of (animName, start, end) tuples in document order,
        or an empty list if no markers are found.
        """
        import re
        markers = []
        for node in nodes:
            if node.type() != "grouplayer":
                continue
            match = re.match(self.ANIM_MARKER_PATTERN, node.name())
            if match:
                animName = match.group(1)
                start = int(match.group(2))
                end = int(match.group(3))
                markers.append((animName, start, end))
                print(f"Animation marker found: '{animName}' frames {start}-{end}")
        return markers

    def _createSpritesheetDocumentFromFrames(self):
        topLevelNodes = self.temporaryDocument.topLevelNodes()
        self._applyLayerExclusion(topLevelNodes)

        markers = self._parseAnimationMarkers(topLevelNodes)

        if markers:
            print(f"Found {len(markers)} animation marker(s) - using marker ranges")
            orderedFrames = self._collectFramesFromMarkers(markers, topLevelNodes)
        else:
            print("No animation markers found - treating entire timeline as 'default'")
            rawFrames = self._collectFramesFromTimeline(topLevelNodes, "default")
            orderedFrames = [(time, animName, self.animationEndTime) for (time, animName) in rawFrames]

        totalFrameCount = len(orderedFrames)
        print(f"Total frames to export: {totalFrameCount}")

        if self.autoCalculateSize:
            maxFrameCount = totalFrameCount
        else:
            maxFrameCount = self.customRowCount * self.customColumnCount

        size = self._getSpritesheetSize(min(totalFrameCount, maxFrameCount))
        self._createSpritesheetDocument(size.columns, size.rows)

        for (time, animName, rangeEnd) in orderedFrames[:maxFrameCount]:
            self.temporaryDocument.setCurrentTime(time)
            self.temporaryDocument.refreshProjection()
            self._convertCurrentFrameToSpritesheetLayer()
            self.exportedFrameTimes.append(time)
            self.exportedFrameAnimations.append(animName)
            self.exportedAnimationRangeEnds.append(rangeEnd)

    def _collectFramesFromMarkers(self, markers, allNodes):
        """
        Collect (time, animName) pairs using explicit marker ranges.
        Marker groups are NOT hidden — art layers live inside them and
        need to composite normally. The groups are purely organisational;
        only their name carries metadata.

        When ignoreEmptyFrames is True, scans the group's child layers for
        keyframes within the range to find only unique drawings, capturing
        hold durations from the gaps between them.
        When ignoreEmptyFrames is False, every frame in the range is exported.
        """
        import re
        allFrames = []
        for (animName, start, end) in markers:
            if self.ignoreEmptyFrames:
                # Find the marker group and scan its children for keyframes
                markerGroup = None
                for node in allNodes:
                    if node.type() == "grouplayer" and re.match(self.ANIM_MARKER_PATTERN, node.name()):
                        match = re.match(self.ANIM_MARKER_PATTERN, node.name())
                        if match and match.group(1) == animName:
                            markerGroup = node
                            break

                if markerGroup is not None:
                    children = markerGroup.childNodes()
                    frames = self._collectFramesFromTimeline(
                        children, animName, rangeStart=start, rangeEnd=end
                    )
                else:
                    # Fallback if group not found
                    frames = [(time, animName) for time in range(start, end + 1)]
            else:
                frames = [(time, animName) for time in range(start, end + 1)]

            # Tag each frame with the marker range end so _exportMetadata
            # can correctly calculate the last keyframe hold duration
            allFrames.extend([(time, animName, end) for (time, animName) in frames])
        return allFrames

    def _collectFramesFromTimeline(self, layers, animName, rangeStart=None, rangeEnd=None):
        """Collect (time, animName) pairs for the given layers and time range."""
        start = rangeStart if rangeStart is not None else self.animationStartTime
        end = rangeEnd if rangeEnd is not None else self.animationEndTime

        if self.autoCalculateSize:
            maxFrameCount = (self.animationEndTime + 1) - self.animationStartTime
        else:
            maxFrameCount = self.customRowCount * self.customColumnCount

        if not self.ignoreEmptyFrames:
            return [(time, animName) for time in range(start, end + 1)]
        else:
            keyframeTimes = set()
            for layer in layers:
                for time in range(start, end + 1):
                    if len(keyframeTimes) >= maxFrameCount:
                        break
                    if self._hasKeyframeAtTime(layer, time):
                        keyframeTimes.add(time)
                        print(f"  [{animName}] keyframe at {time}")
            return [(time, animName) for time in sorted(keyframeTimes)]

    def _createSpritesheetDocument(self, columns, rows):
        self.spritesheetColumns = columns
        self.spritesheetRows = rows

        self.spritesheetDocument = self.krita.createDocument(
            columns * self.temporaryDocument.width(), 
            rows * self.temporaryDocument.height(), 
            "Spritesheet", 
            self.temporaryDocument.colorModel(), 
            self.temporaryDocument.colorDepth(), 
            self.temporaryDocument.colorProfile(), 
            self.temporaryDocument.resolution())
        
        self.spritesheetDocument.setBatchmode(True)

        # Remove any default layers
        layers = self.spritesheetDocument.topLevelNodes()
        for layer in layers:
            layer.remove()
        
        print(f"Spritesheet document created with {columns} columns and {rows} rows")
        print(f"Spritesheet document width: {self.spritesheetDocument.width()}")
        print(f"Spritesheet document height: {self.spritesheetDocument.height()}")

    def _getSpritesheetSize(self, frameCount):
        Size = namedtuple("Size", ["columns", "rows"])

        if frameCount == 0:
            return Size(1, 1)
        elif self.spritesheetType == "Horizontal Strip":
            return Size(frameCount, 1)
        elif self.spritesheetType == "Vertical Strip":
            return Size(1, frameCount)
        elif self.autoCalculateSize == False:
            return Size(self.customColumnCount, self.customRowCount)
        elif self.spritesheetType == "Rows":
            columnCount = math.ceil(math.sqrt(frameCount))
            return Size(columnCount, math.ceil(frameCount / columnCount))
        elif self.spritesheetType == "Columns":
            rowCount = math.ceil(math.sqrt(frameCount))
            return Size(math.ceil(frameCount / rowCount), rowCount)
        
        else:
            raise Exception(f"Invalid spritesheet type provided: {self.spritesheetType}")

    def _convertCurrentFrameToSpritesheetLayer(self):
        # Ensure that operations on the temporary document have finished
        # before attempting to retrieve its pixel data.
        self.temporaryDocument.waitForDone()

        width = self.temporaryDocument.width()
        height = self.temporaryDocument.height()

        # Copy the pixel data of the current frame displayed on the temporary document
        currentFramePixelData = self.temporaryDocument.pixelData(0, 0, width, height)

        # Convert the pixel data of the current frame into a layer in the spritesheet document.
        newSpritesheetLayer = self.spritesheetDocument.createNode(str(len(self.spritesheetDocument.topLevelNodes())), "paintlayer")
        self.spritesheetDocument.rootNode().addChildNode(newSpritesheetLayer, None)
        newSpritesheetLayer.setPixelData(currentFramePixelData, 0, 0, width, height)

        self.spritesheetDocument.refreshProjection()

    def _hasKeyframeAtTime(self, layer, time):
        if not layer.visible():
            return False

        if layer.hasKeyframeAtTime(time):
            return True
            
        if len(layer.childNodes()) != 0:
            # check if any of the child nodes
            # have a keyframe at the given time
            for child in layer.childNodes():
                if self._hasKeyframeAtTime(child, time):
                    return True
                
        # reaching this point means that the frame
        # is not a keyframe in the parent layer or
        # any of its children.
        return False
    
    def _positionFramesInSpritesheetDocument(self):
        # Based on the selected spritesheet type, move all of the layers into their respective
        # positions in the spritesheet document.
        if self.spritesheetType == "Rows":
            self._positionSpritesheetFramesByRows()
        elif self.spritesheetType == "Columns":
            self._positionSpritesheetFramesByColumns()
        elif self.spritesheetType == "Horizontal Strip":
            self._positionSpritesheetFramesAsHorizontalStrip()
        elif self.spritesheetType == "Vertical Strip":
            self._positionSpritesheetFramesAsVerticalStrip()
        else:
            raise Exception(f"Invalid spritesheet type provided: {self.spritesheetType}")
            
        self.spritesheetDocument.refreshProjection()

    def _positionSpritesheetFramesByRows(self):
         # Place sprites by filling up each row before moving to the next row.
         layers = self.spritesheetDocument.topLevelNodes()
         for index in range(len(layers)):
             layers[index].move(int(index % self.spritesheetColumns) * self.finalSpriteWidth, 
                                int(index / self.spritesheetColumns) * self.finalSpriteHeight)

    def _positionSpritesheetFramesByColumns(self):
         # Place sprites by filling up each column before moving to the next column.
         layers = self.spritesheetDocument.topLevelNodes()
         for index in range(len(layers)):
             layers[index].move(int(index / self.spritesheetRows) * self.finalSpriteWidth, 
                                int(index % self.spritesheetRows) * self.finalSpriteHeight)

    def _positionSpritesheetFramesAsHorizontalStrip(self):
        # Place sprites in a single horizontal line.
        layers = self.spritesheetDocument.topLevelNodes()
        for index in range(len(layers)):
            layers[index].move(index * self.finalSpriteWidth, 0)

    def _positionSpritesheetFramesAsVerticalStrip(self):
        # Place sprites in a single vertical line.
        layers = self.spritesheetDocument.topLevelNodes()
        for index in range(len(layers)):
            layers[index].move(0, index * self.finalSpriteHeight)

    def _exportMetadata(self):
        fps = self.activeDocument.framesPerSecond()
        spritesheetName = Path(self.exportFilePath).name

        # Group exported frames by animation name, preserving order.
        # animationsMap: { animName: [(spritesheetIndex, time), ...] }
        animationsMap = {}
        seenNames = []
        for i, (time, animName) in enumerate(zip(self.exportedFrameTimes, self.exportedFrameAnimations)):
            if animName not in animationsMap:
                animationsMap[animName] = []
                seenNames.append(animName)
            animationsMap[animName].append((i, time))

        # Build the animations array.
        # When ignoreEmptyFrames is True, frames are keyframe-detected and the gap
        # between keyframes defines the hold duration — so per-frame durations vary.
        # When ignoreEmptyFrames is False, every frame is 1 timeline frame long.
        animations = []
        for animName in seenNames:
            framePairs = animationsMap[animName]
            frames = []
            for j, (spritesheetIndex, time) in enumerate(framePairs):
                if self.ignoreEmptyFrames:
                    # Duration is the gap to the next keyframe in this animation
                    if j + 1 < len(framePairs):
                        nextTime = framePairs[j + 1][1]
                    else:
                        # Last keyframe: hold until the marker range end + 1
                        # so the full hold is preserved (e.g. last key at 31,
                        # range ends at 34 → holds for 3 frames as expected)
                        rangeEnd = self.exportedAnimationRangeEnds[spritesheetIndex]
                        nextTime = rangeEnd + 1
                    durationFrames = nextTime - time
                else:
                    durationFrames = 1
                frames.append({
                    "index": spritesheetIndex,
                    "timelineFrame": time,
                    "durationFrames": durationFrames,
                    "durationSeconds": round(durationFrames / fps, 6)
                })
            animations.append({
                "name": animName,
                "frameCount": len(frames),
                "frames": frames
            })

        metadata = {
            "spritesheet": spritesheetName,
            "fps": fps,
            "frameWidth": self.finalSpriteWidth,
            "frameHeight": self.finalSpriteHeight,
            "columns": self.spritesheetColumns,
            "rows": self.spritesheetRows,
            "animations": animations
        }

        metadataPath = Path(self.exportFilePath).with_suffix(".json")
        with open(metadataPath, "w") as f:
            json.dump(metadata, f, indent=4)

        print(f"Metadata exported to {metadataPath} with {len(animations)} animation(s)")

    def _forceCloseDocument(self, document):
        document.close()

    def _exportToFile(self):
        # Ensure that operations in the spritesheet document have finished
        # before attempting to retrieve its pixel data.
        self.spritesheetDocument.waitForDone()

        # Export the spritesheet
        self.spritesheetDocument.exportImage(self.exportFilePath, krita.InfoObject())
        print(f"Spritesheet generated at {self.exportFilePath}")
