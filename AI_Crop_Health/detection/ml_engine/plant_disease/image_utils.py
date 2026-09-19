"""
RELAXED Image Validation for Plant Disease Diagnosis
----------------------------------------------------
Accepts most reasonable plant images while filtering obvious garbage.
Prioritizes getting images to the model over rejection.
"""

import os
import numpy as np
from PIL import Image, ImageStat
import cv2
from pathlib import Path


class ImageValidationError(Exception):
    """Custom exception for image validation failures."""
    pass


class ImageValidator:
    """
    RELAXED image validator for plant disease diagnosis.
    Accepts most images, only rejects obvious non-images or corrupt files.
    """

    # File validation
    ALLOWED_FORMATS = {'JPEG', 'JPG', 'PNG'}
    MAX_FILE_SIZE_MB = 10
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

    # Resolution thresholds (VERY RELAXED)
    MIN_RESOLUTION = 100  # Very low minimum - accept phone cameras
    MAX_RESOLUTION = 5000  # Allow high-res cameras

    # Quality thresholds (RELAXED)
    MIN_BRIGHTNESS = 30   # Accept darker images
    MAX_BRIGHTNESS = 240  # Accept brighter images
    MIN_SHARPNESS_SCORE = 5  # VERY relaxed blur detection

    # Leaf detection (DISABLED - let model decide)
    MIN_GREEN_RATIO = 0.05  # Almost any color accepted
    MIN_LEAF_TEXTURE_SCORE = 20  # Very low requirement
    MAX_ASPECT_RATIO = 5.0  # Accept wider images
    
    def __init__(self):
        """Initialize validator."""
        pass

    def _check_file_validity(self, image_file):
        """
        Validate file properties before attempting to open as image.

        Args:
            image_file: Django UploadedFile or file-like object

        Returns:
            dict: {'passed': bool, 'reason': str}
        """
        # Check if file exists
        if image_file is None:
            return {'passed': False, 'reason': 'No image file provided'}

        # Check file size
        try:
            file_size = image_file.size if hasattr(image_file, 'size') else len(image_file.read())
            if hasattr(image_file, 'seek'):
                image_file.seek(0)  # Reset file pointer
        except:
            return {'passed': False, 'reason': 'Unable to read file size'}

        if file_size > self.MAX_FILE_SIZE_BYTES:
            return {
                'passed': False,
                'reason': f'Image file too large ({file_size/1024/1024:.1f}MB). Maximum allowed: {self.MAX_FILE_SIZE_MB}MB'
            }

        # Check file extension
        try:
            filename = image_file.name if hasattr(image_file, 'name') else str(image_file)
            extension = Path(filename).suffix.upper().lstrip('.')
            if extension not in self.ALLOWED_FORMATS:
                return {
                    'passed': False,
                    'reason': f'Unsupported file format: {extension}. Allowed formats: {", ".join(self.ALLOWED_FORMATS)}'
                }
        except:
            # If we can't determine format, allow it (let PIL try)
            pass

        return {'passed': True, 'reason': 'File format and size acceptable'}

    def _check_resolution(self, image):
        """Check if image meets minimum resolution requirements."""
        width, height = image.size
        min_dimension = min(width, height)

        # Only reject extremely small images
        if min_dimension < self.MIN_RESOLUTION:
            return {
                'passed': False,
                'reason': f'Image too small ({width}x{height}). Minimum {self.MIN_RESOLUTION}px required.',
                'metrics': {'width': width, 'height': height}
            }

        return {
            'passed': True,
            'reason': f'Resolution acceptable ({width}x{height})',
            'metrics': {'width': width, 'height': height}
        }
    
    def _check_brightness(self, image):
        """Check if image has acceptable brightness (very relaxed)."""
        grayscale = image.convert('L')
        stat = ImageStat.Stat(grayscale)
        mean_brightness = stat.mean[0]

        # Only reject extremely dark or bright images
        if mean_brightness < self.MIN_BRIGHTNESS:
            return {
                'passed': False,
                'reason': f'Image extremely dark (brightness: {mean_brightness:.0f}/255). Use better lighting.',
                'metrics': {'brightness': mean_brightness}
            }

        if mean_brightness > self.MAX_BRIGHTNESS:
            return {
                'passed': False,
                'reason': f'Image overexposed (brightness: {mean_brightness:.0f}/255). Reduce lighting.',
                'metrics': {'brightness': mean_brightness}
            }

        return {
            'passed': True,
            'reason': f'Brightness OK ({mean_brightness:.0f}/255)',
            'metrics': {'brightness': mean_brightness}
        }
    
    def _check_sharpness(self, image):
        """Detect only severe blur."""
        try:
            img_array = np.array(image.convert('RGB'))
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

            # Only reject extremely blurry images
            if laplacian_var < self.MIN_SHARPNESS_SCORE:
                return {
                    'passed': False,
                    'reason': f'Image severely blurry (score: {laplacian_var:.0f}). Hold camera steady.',
                    'metrics': {'sharpness': laplacian_var}
                }

            return {
                'passed': True,
                'reason': f'Sharpness OK ({laplacian_var:.0f})',
                'metrics': {'sharpness': laplacian_var}
            }
        except:
            # If sharpness check fails, pass anyway
            return {'passed': True, 'reason': 'Sharpness check skipped', 'metrics': {'sharpness': 0}}
    
    def validate(self, image_file):
        """
        RELAXED validation - accepts most images.
        Only rejects corrupt files or extreme quality issues.

        Args:
            image_file: Django UploadedFile or file-like object

        Returns:
            dict with keys:
                - is_valid (bool): True if image is acceptable
                - reason (str): Human-readable validation result
                - details (dict): Detailed validation metrics
                - quality_score (int): Overall quality score (0-100)
        """
        try:
            # Step 1: Check file validity
            file_check = self._check_file_validity(image_file)
            if not file_check['passed']:
                return {
                    'is_valid': False,
                    'reason': file_check['reason'],
                    'details': {},
                    'metrics': {},
                    'quality_score': 0
                }

            # Step 2: Open image
            try:
                if hasattr(image_file, 'seek'):
                    image_file.seek(0)
                image = Image.open(image_file)
                image.verify()  # Check if corrupt
                if hasattr(image_file, 'seek'):
                    image_file.seek(0)
                image = Image.open(image_file)  # Reopen after verify
            except Exception as e:
                return {
                    'is_valid': False,
                    'reason': f'Corrupted or invalid image file: {str(e)}',
                    'details': {},
                    'metrics': {},
                    'quality_score': 0
                }

            # Step 3: Basic checks (resolution, brightness)
            resolution_check = self._check_resolution(image)
            if not resolution_check['passed']:
                return {
                    'is_valid': False,
                    'reason': resolution_check['reason'],
                    'details': {'resolution': resolution_check.get('metrics', {})},
                    'metrics': resolution_check.get('metrics', {}),
                    'quality_score': 0
                }

            brightness_check = self._check_brightness(image)
            if not brightness_check['passed']:
                return {
                    'is_valid': False,
                    'reason': brightness_check['reason'],
                    'details': {'brightness': brightness_check.get('metrics', {})},
                    'metrics': brightness_check.get('metrics', {}),
                    'quality_score': 0
                }

            # Step 4: Optional sharpness check (very lenient)
            sharpness_check = self._check_sharpness(image)
            # DON'T fail on sharpness - just record it
            
            # Calculate quality score (informational only)
            metrics = {}
            metrics.update(brightness_check.get('metrics', {}))
            metrics.update(sharpness_check.get('metrics', {}))
            metrics.update(resolution_check.get('metrics', {}))
            
            quality_score = 75  # Default score for accepted images
            
            # Brightness contributes 25 points
            brightness = metrics.get('brightness', 135)
            if 60 <= brightness <= 200:
                quality_score += 10
            
            # Sharpness contributes 15 points
            sharpness = metrics.get('sharpness', 0)
            if sharpness >= 50:
                quality_score += 15
            elif sharpness >= 20:
                quality_score += 10
            
            quality_score = min(100, quality_score)

            # ACCEPT THE IMAGE
            return {
                'is_valid': True,
                'reason': 'Image accepted for diagnosis',
                'details': {
                    'brightness': brightness_check.get('metrics', {}),
                    'sharpness': sharpness_check.get('metrics', {}),
                    'resolution': resolution_check.get('metrics', {})
                },
                'metrics': metrics,
                'quality_score': quality_score
            }

        except ImageValidationError as e:
            return {
                'is_valid': False,
                'reason': str(e),
                'details': {},
                'metrics': {},
                'quality_score': 0
            }

        except Exception as e:
            # Unknown error - ACCEPT anyway (let model try)
            return {
                'is_valid': True,
                'reason': f'Validation skipped due to error, accepting image',
                'details': {},
                'metrics': {},
                'quality_score': 50
            }
    
    def get_quality_recommendations(self, validation_result):
        """
        Generate user-friendly recommendations based on validation result.

        Args:
            validation_result: Result from validate() method

        Returns:
            list: User-friendly recommendation strings
        """
        if validation_result.get('is_valid', False):
            score = validation_result.get('quality_score', 0)
            if score >= 90:
                return [
                    "✅ Excellent image quality!",
                    "Ready for diagnosis"
                ]
            elif score >= 70:
                return [
                    "✅ Image accepted for diagnosis",
                    "Quality is good enough for processing"
                ]
            else:
                return [
                    "✅ Image accepted",
                    "Note: Image quality could be improved for better results"
                ]

        # Rejection recommendations
        recommendations = []
        reason = validation_result.get('reason', '').lower()

        if 'resolution' in reason or 'too small' in reason:
            recommendations.extend([
                "❌ Image too small",
                "• Move camera closer to the plant",
                "• Use camera zoom or get within 6-12 inches",
                f"• Minimum size required: {self.MIN_RESOLUTION}x{self.MIN_RESOLUTION} pixels"
            ])

        elif 'dark' in reason or 'brightness' in reason:
            recommendations.extend([
                "❌ Image too dark",
                "• Use better lighting (natural daylight preferred)",
                "• Turn on camera flash if indoors",
                "• Take photo during daytime"
            ])

        elif 'overexposed' in reason:
            recommendations.extend([
                "❌ Image overexposed",
                "• Avoid direct sunlight on leaves",
                "• Use shade or photograph in cloudy weather"
            ])

        elif 'file too large' in reason:
            recommendations.extend([
                f"❌ File size too large (max: {self.MAX_FILE_SIZE_MB}MB)",
                "• Resize/compress the image",
                "• Use lower camera resolution setting"
            ])

        elif 'unsupported' in reason or 'format' in reason:
            recommendations.extend([
                "❌ Unsupported file format",
                f"• Allowed formats: {', '.join(self.ALLOWED_FORMATS)}",
                "• Convert to JPG or PNG format"
            ])

        elif 'corrupt' in reason:
            recommendations.extend([
                "❌ Corrupted image file",
                "• Try uploading the image again",
                "• Use a different image"
            ])

        else:
            recommendations.extend([
                "❌ Upload failed",
                "• Ensure image is a valid JPG or PNG",
                "• Check file is not corrupted",
                "• Try again with a different image"
            ])

        return recommendations