import requests
from PIL import Image, ImageDraw, ImageFont
import io
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Dict, Tuple, Union
import os
import numpy as np
from datetime import datetime

class ImageAnnotationCropper:
    def __init__(self, image_data_list: Union[dict, List[dict]]):
        """
        Initialize with single image data or list of image data containing annotations
        
        Args:
            image_data_list: Single image data dict or list of image data dicts
        """
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initializing ImageAnnotationCropper...")

        if isinstance(image_data_list, dict):
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Converting single dict to list format")
            image_data_list = [image_data_list]
        
        self.image_data_list = image_data_list
        self.images = []  # Will store (image_data, PIL_Image) tuples
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Initialized with {len(self.image_data_list)} image(s)")
        
    def download_images(self):
        """Download all images from URLs"""
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting download of {len(self.image_data_list)} images...")
        
        for idx, image_data in enumerate(self.image_data_list):
            try:
                print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Downloading image {idx+1}/{len(self.image_data_list)}...")
                response = requests.get(image_data['url'])
                response.raise_for_status()
                pil_image = Image.open(io.BytesIO(response.content))
                self.images.append((image_data, pil_image))
                print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ [{idx+1}/{len(self.image_data_list)}] Downloaded: {image_data['info']['width']}x{image_data['info']['height']} ({len(response.content)} bytes)")
            except Exception as e:
                print(f"[ERROR] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✗ [{idx+1}/{len(self.image_data_list)}] Error downloading image: {e}")
                # Store None for failed downloads
                self.images.append((image_data, None))
        
        successful = sum(1 for _, img in self.images if img is not None)
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✓ Download complete: {successful}/{len(self.image_data_list)} images successfully downloaded\n")
        return self.images
    
    def flatten_points(self, points: Union[List[float], List[List[float]]]) -> List[float]:
        """
        Flatten nested point lists into a single flat list
        Handles both [x1, y1, x2, y2] and [[x1, y1], [x2, y2]] formats
        """
        flat_points = []
        for point in points:
            if isinstance(point, list):
                flat_points.extend(point)
            else:
                flat_points.append(point)
        return flat_points
    
    def denormalize_coordinates(self, normalized_points: Union[List[float], List[List[float]]], 
                               image_width: int, image_height: int) -> List[int]:
        """
        Convert normalized coordinates (0-1) to pixel coordinates
        Handles both flat and nested point lists
        Works for all shape types: Rectangle, Polygon, Point, Line, etc.
        """
        flat_points = self.flatten_points(normalized_points)
        
        if len(flat_points) % 2 != 0:
            print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Odd number of coordinate values: {len(flat_points)}, truncating last value")
            flat_points = flat_points[:-1]
        
        pixel_coords = []
        for i in range(0, len(flat_points), 2):
            if i + 1 >= len(flat_points):
                break
            # Clamp normalized coordinates to [0, 1] range
            x_norm = max(0.0, min(1.0, float(flat_points[i])))
            y_norm = max(0.0, min(1.0, float(flat_points[i + 1])))
            x = int(x_norm * image_width)
            y = int(y_norm * image_height)
            pixel_coords.extend([x, y])
        return pixel_coords
    
    def get_bounding_box(self, points: Union[List[float], List[List[float]]], 
                        image_width: int, image_height: int) -> Tuple[int, int, int, int]:
        """
        Get bounding box from annotation points (normalized coordinates)
        Works for all shape types: Rectangle, Polygon, Point, Line, etc.
        Returns: (x_min, y_min, x_max, y_max) in pixel coordinates
        """
        pixel_coords = self.denormalize_coordinates(points, image_width, image_height)
        
        if len(pixel_coords) < 2:
            print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Insufficient coordinates for bounding box: {len(pixel_coords)}")
            return None
        
        # Extract x and y coordinates separately
        x_coords = [pixel_coords[i] for i in range(0, len(pixel_coords), 2)]
        y_coords = [pixel_coords[i] for i in range(1, len(pixel_coords), 2)]
        
        # Validate coordinates
        if not x_coords or not y_coords:
            print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Empty coordinate lists for bounding box")
            return None
        
        # Calculate bounding box (works for any shape type)
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        
        # Clamp to image boundaries
        x_min = max(0, min(x_min, image_width - 1))
        y_min = max(0, min(y_min, image_height - 1))
        x_max = max(0, min(x_max, image_width - 1))
        y_max = max(0, min(y_max, image_height - 1))
        
        bbox = (x_min, y_min, x_max, y_max)
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bounding box computed: {bbox} (size: {bbox[2]-bbox[0]}x{bbox[3]-bbox[1]})")
        return bbox
    
    def expand_bbox(self, bbox: Tuple[int, int, int, int], 
                    image_width: int, image_height: int,
                    padding_percent: float = 0.2,
                    min_size: int = 50) -> Tuple[int, int, int, int]:
        """
        Expand bounding box by a percentage for better context
        Ensures minimum size for very small annotations
        """
        x_min, y_min, x_max, y_max = bbox
        width = x_max - x_min
        height = y_max - y_min
        
        # Ensure minimum size
        if width < min_size:
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Width {width} < min_size {min_size}, expanding to minimum")
            center_x = (x_min + x_max) // 2
            x_min = center_x - min_size // 2
            x_max = center_x + min_size // 2
            width = min_size
            
        if height < min_size:
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Height {height} < min_size {min_size}, expanding to minimum")
            center_y = (y_min + y_max) // 2
            y_min = center_y - min_size // 2
            y_max = center_y + min_size // 2
            height = min_size
        
        padding_x = int(width * padding_percent)
        padding_y = int(height * padding_percent)
        
        # Expand and clamp to image boundaries
        x_min = max(0, x_min - padding_x)
        y_min = max(0, y_min - padding_y)
        x_max = min(image_width, x_max + padding_x)
        y_max = min(image_height, y_max + padding_y)
        
        expanded_bbox = (x_min, y_min, x_max, y_max)
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Expanded bbox: {expanded_bbox} (final size: {expanded_bbox[2]-expanded_bbox[0]}x{expanded_bbox[3]-expanded_bbox[1]})")
        return expanded_bbox
    
    def crop_annotation(self, image: Image.Image, annotation: dict, 
                       image_width: int, image_height: int,
                       padding_percent: float = 0.2) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
        """
        Crop the image around an annotation with padding
        Returns None if cropping fails
        """
        try:
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cropping annotation {annotation['id']}")
            points = annotation['points']
            bbox = self.get_bounding_box(points, image_width, image_height)
            
            if bbox is None:
                print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Invalid bounding box for annotation {annotation['id']}")
                return None, None
            
            expanded_bbox = self.expand_bbox(bbox, image_width, image_height, padding_percent)
            
            # Validate bbox
            if expanded_bbox[2] <= expanded_bbox[0] or expanded_bbox[3] <= expanded_bbox[1]:
                print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Invalid bbox dimensions for annotation {annotation['id']}")
                return None, None
            
            cropped = image.crop(expanded_bbox)
            
            # Verify cropped image is valid
            if cropped.size[0] == 0 or cropped.size[1] == 0:
                print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Zero-size crop for annotation {annotation['id']}")
                return None, None
            
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Successfully cropped annotation {annotation['id']}, size: {cropped.size[0]}x{cropped.size[1]}")
            return cropped, expanded_bbox
            
        except Exception as e:
            print(f"[ERROR] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Failed to crop annotation {annotation['id']}: {e}")
            return None, None
    
    def draw_annotation_on_image(self, image: Image.Image, annotation: dict,
                                image_width: int, image_height: int,
                                bbox: Tuple[int, int, int, int] = None) -> Image.Image:
        """
        Draw annotation overlay on image
        """
        try:
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Drawing annotation {annotation['id']} on image (shape type: {annotation['shape']})")
            img_copy = image.copy()
            draw = ImageDraw.Draw(img_copy, 'RGBA')
            
            points = annotation['points']
            shape = annotation['shape']
            color = annotation['annotation_class']['annotation_class_color']
            
            # Convert hex color to RGB
            color_rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            fill_color = color_rgb + (80,)  # Add alpha for transparency
            outline_color = color_rgb + (255,)
            
            pixel_coords = self.denormalize_coordinates(points, image_width, image_height)
            
            # Adjust coordinates if drawing on cropped image
            if bbox:
                x_offset, y_offset = bbox[0], bbox[1]
                pixel_coords = [
                    pixel_coords[i] - x_offset if i % 2 == 0 else pixel_coords[i] - y_offset
                    for i in range(len(pixel_coords))
                ]
            
            # Draw based on shape type
            if shape == 3:  # Rectangle
                if len(pixel_coords) >= 4:
                    draw.rectangle(
                        [(pixel_coords[0], pixel_coords[1]), 
                         (pixel_coords[2], pixel_coords[3])],
                        outline=outline_color,
                        fill=fill_color,
                        width=3
                    )
                else:
                    print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Rectangle annotation {annotation['id']} has insufficient points: {len(pixel_coords)}")
            elif shape == 4:  # Polygon
                coords_list = [(pixel_coords[i], pixel_coords[i+1]) 
                              for i in range(0, len(pixel_coords), 2)]
                if len(coords_list) >= 3:
                    draw.polygon(coords_list, outline=outline_color, fill=fill_color, width=3)
                else:
                    print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Polygon annotation {annotation['id']} has insufficient points: {len(coords_list)}")
            elif shape == 8:  # Point
                if len(pixel_coords) >= 2:
                    radius = 15
                    draw.ellipse(
                        [(pixel_coords[0]-radius, pixel_coords[1]-radius),
                         (pixel_coords[0]+radius, pixel_coords[1]+radius)],
                        outline=outline_color,
                        fill=fill_color,
                        width=3
                    )
                else:
                    print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Point annotation {annotation['id']} has insufficient points: {len(pixel_coords)}")
            elif shape == 5:  # Line/Polyline
                coords_list = [(pixel_coords[i], pixel_coords[i+1]) 
                              for i in range(0, len(pixel_coords), 2)]
                if len(coords_list) >= 2:
                    draw.line(coords_list, fill=outline_color, width=3)
                else:
                    print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Line annotation {annotation['id']} has insufficient points: {len(coords_list)}")
            else:
                # Fallback for unknown shape types: draw bounding box
                print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unknown shape type {shape} for annotation {annotation['id']}, drawing bounding box")
                coords_list = [(pixel_coords[i], pixel_coords[i+1]) 
                              for i in range(0, len(pixel_coords), 2)]
                if len(coords_list) >= 2:
                    x_coords = [pixel_coords[i] for i in range(0, len(pixel_coords), 2)]
                    y_coords = [pixel_coords[i] for i in range(1, len(pixel_coords), 2)]
                    if x_coords and y_coords:
                        draw.rectangle(
                            [(min(x_coords), min(y_coords)), 
                             (max(x_coords), max(y_coords))],
                            outline=outline_color,
                            fill=fill_color,
                            width=3
                        )
            
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Successfully drew annotation {annotation['id']}")
            return img_copy
            
        except Exception as e:
            print(f"[ERROR] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Failed to draw annotation {annotation['id']}: {e}")
            return image
    
    def create_visualization(self, output_path: str = 'annotation_crops.png', 
                           padding_percent: float = 0.2):
        """
        Create a visualization showing all images with their cropped annotations
        """
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting visualization creation...")
        if not self.images:
            self.download_images()
        
        # Process each image
        for img_idx, (image_data, pil_image) in enumerate(self.images):
            if pil_image is None:
                print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Skipping image {img_idx + 1} (download failed)")
                continue
            
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Processing image {img_idx + 1} for visualization...")
            image_width = image_data['info']['width']
            image_height = image_data['info']['height']
            annotations = image_data['annotations']
            
            # Filter out visible annotations only
            visible_annotations = [ann for ann in annotations if ann.get('visible', True)]
            
            if len(visible_annotations) == 0:
                print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No visible annotations found in image {img_idx + 1}!")
                continue
            
            # Create output path for this image
            base_path = output_path.rsplit('.', 1)
            if len(base_path) == 2:
                img_output_path = f"{base_path[0]}_image_{img_idx + 1}.{base_path[1]}"
            else:
                img_output_path = f"{output_path}_image_{img_idx + 1}.png"
            
            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(img_output_path) if os.path.dirname(img_output_path) else '.'
            os.makedirs(output_dir, exist_ok=True)
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Output directory ready: {output_dir}")
            
            # Pre-process crops to filter out failed ones
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Processing {len(visible_annotations)} visible annotations...")
            successful_crops = []
            for ann in visible_annotations:
                cropped_img, crop_bbox = self.crop_annotation(
                    pil_image, ann, image_width, image_height, padding_percent
                )
                if cropped_img is not None and crop_bbox is not None:
                    successful_crops.append((ann, cropped_img, crop_bbox))
            
            if len(successful_crops) == 0:
                print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No valid crops could be created for image {img_idx + 1}!")
                continue
            
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Image {img_idx + 1}: Successfully cropped {len(successful_crops)}/{len(visible_annotations)} annotations")
            
            # Create figure with subplots
            cols = 3
            rows = 1 + ((len(successful_crops) + cols - 1) // cols)
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Creating visualization figure: {rows} rows x {cols} cols")
            
            fig = plt.figure(figsize=(18, 5 * rows))
            
            # Plot original image with all annotations (spans first row)
            ax1 = plt.subplot(rows, cols, (1, cols))
            ax1.set_title(f'Image {img_idx + 1}: Original with All Annotations', 
                         fontsize=16, fontweight='bold')
            
            original_with_annotations = pil_image.copy()
            for ann in visible_annotations:
                original_with_annotations = self.draw_annotation_on_image(
                    original_with_annotations, ann, image_width, image_height
                )
            
            ax1.imshow(original_with_annotations)
            ax1.axis('off')
            
            # Add legend
            legend_items = []
            for ann, _, _ in successful_crops:
                class_name = ann['annotation_class']['annotation_class_long_name']
                ann_id = ann['id']
                legend_items.append(f"ID {ann_id}: {class_name}")
            
            legend_text = "Annotations:\n" + "\n".join(legend_items[:10])
            if len(legend_items) > 10:
                legend_text += f"\n... and {len(legend_items) - 10} more"
            
            ax1.text(1.02, 0.5, legend_text, transform=ax1.transAxes,
                    fontsize=9, verticalalignment='center',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            # Plot each successful crop
            for idx, (ann, cropped_img, crop_bbox) in enumerate(successful_crops):
                ax = plt.subplot(rows, cols, cols + idx + 1)
                
                # Draw annotation on crop
                cropped_with_annotation = self.draw_annotation_on_image(
                    cropped_img, ann, image_width, image_height, crop_bbox
                )
                
                # Title with annotation details
                class_name = ann['annotation_class']['annotation_class_long_name']
                ann_id = ann['id']
                area = ann.get('area', 0)
                condition = ann.get('condition', {}).get('rating_name', 'N/A')
                
                title = f"ID: {ann_id} - {class_name}"
                if area > 0:
                    title += f"\nArea: {area:.1f} sq units"
                if condition != 'N/A':
                    title += f"\nCondition: {condition}"
                
                ax.set_title(title, fontsize=10, fontweight='bold')
                ax.imshow(cropped_with_annotation)
                ax.axis('off')
            
            plt.tight_layout()
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Saving visualization to {img_output_path}...")
            plt.savefig(img_output_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Visualization saved to {img_output_path}\n")
        
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Visualization creation complete")
        return True
    
    def save_individual_crops(self, output_dir: str = 'crops', 
                            padding_percent: float = 0.2):
        """
        Save each cropped annotation as individual image files for all images
        """
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting to save individual crops to directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Output directory created/verified: {output_dir}")
        
        if not self.images:
            self.download_images()
        
        total_saved = 0
        total_annotations = 0
        
        for img_idx, (image_data, pil_image) in enumerate(self.images):
            if pil_image is None:
                print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Skipping image {img_idx + 1} (download failed)")
                continue
            
            image_width = image_data['info']['width']
            image_height = image_data['info']['height']
            annotations = image_data['annotations']
            
            visible_annotations = [ann for ann in annotations if ann.get('visible', True)]
            total_annotations += len(visible_annotations)
            
            print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Processing Image {img_idx + 1}: {len(visible_annotations)} visible annotations")
            
            for idx, ann in enumerate(visible_annotations):
                class_name = ann['annotation_class']['annotation_class_name']
                ann_id = ann['id']
                
                # Crop and mark
                cropped_img, bbox = self.crop_annotation(
                    pil_image, ann, image_width, image_height, padding_percent
                )
                
                if cropped_img is None or bbox is None:
                    print(f"[WARNING] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Skipping annotation {ann_id} (crop failed)")
                    continue
                
                cropped_with_annotation = self.draw_annotation_on_image(
                    cropped_img, ann, image_width, image_height, bbox
                )
                
                # Save with image index in filename
                filename = f"{output_dir}/img{img_idx + 1}_crop_{ann_id}_{class_name}.jpg"
                cropped_with_annotation.save(filename, quality=95)
                total_saved += 1
                print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Saved: {filename}")
        
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Total crops saved: {total_saved}/{total_annotations} across {len(self.images)} images")
        return total_saved
    
    def get_summary(self):
        """
        Get summary statistics for all images
        """
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Generating summary statistics...")
        if not self.images:
            self.download_images()
        
        summary = {
            'total_images': len(self.image_data_list),
            'successful_downloads': sum(1 for _, img in self.images if img is not None),
            'failed_downloads': sum(1 for _, img in self.images if img is None),
            'images': []
        }
        
        for img_idx, (image_data, pil_image) in enumerate(self.images):
            img_info = {
                'index': img_idx + 1,
                'downloaded': pil_image is not None,
                'width': image_data['info']['width'],
                'height': image_data['info']['height'],
                'total_annotations': len(image_data['annotations']),
                'visible_annotations': len([ann for ann in image_data['annotations'] if ann.get('visible', True)])
            }
            summary['images'].append(img_info)
        
        print(f"[INFO] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Summary generated: {summary['total_images']} images, {summary['successful_downloads']} successful downloads, {summary['failed_downloads']} failed downloads")
        return summary