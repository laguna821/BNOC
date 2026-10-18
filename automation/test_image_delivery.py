"""Delivery tests use synthetic fixtures, never certify real illustration quality."""
import copy
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zlib
from bible import digest
import image_delivery
import render
import test_editorial

WEBP=b'RIFF'+(12).to_bytes(4,'little')+b'WEBPVP8 '+b'fixture'

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.f=test_editorial.EditorialTests();self.f.setUp();self.root=self.f.root
        self.source=b'\x89PNG\r\n\x1a\n'+b'fixture-original'*100
        (self.root/'scene.png').write_bytes(self.source)
        self.f.m['figures']=[dict(id='scene',file='scene.png',kind='generated-illustration',alt='fixture',caption='fixture',
            sha256=digest(self.source),inspection=dict(sha256=digest(self.source),reviewedAt='2026-10-18T07:02:00+00:00',evidence='Fixture inspection only'),
            provenance=dict(tool='test-fixture',prompt='Fixture only',generatedAt='2026-10-18T07:01:00+00:00',originalSha256=digest(self.source)))]
        self.f.m['sections'][0]['cards'][0]['figure']='scene'
        self.f.plan.update(mode='illustrated',items=[dict(id='scene',kind='generated-illustration',at='reading',purpose='fixture')]);self.f.save()
    def tearDown(self):self.f.tearDown()
    def encoder(self,source,target,config,quality,lossless):
        target.write_bytes(WEBP)
        return dict(width=64,height=32,sourceWidth=64,sourceHeight=32,sourceHasAlpha=True,hasAlpha=True,sharpVersion='fixture')
    def test_derivative_keeps_prose_original_and_requires_new_inspection(self):
        render.validate(self.f.m,self.f.passage,self.root)
        with mock.patch.object(image_delivery,'encode',side_effect=self.encoder):
            m,report=image_delivery.optimize(self.f.m,self.root,{})
        self.assertEqual(report['changedFigures'],1)
        self.assertFalse(report['automaticVisualApproval'])
        self.assertEqual((self.root/'scene.png').read_bytes(),self.source)
        self.assertEqual(m['sections'],self.f.m['sections'])
        self.assertEqual(m['figures'][0]['provenance']['originalSha256'],digest(self.source))
        self.assertFalse(m['figures'][0]['inspection']['evidence'])
        with self.assertRaisesRegex(ValueError,'actually inspected'):
            render.validate(m,self.f.passage,self.root)
        figure=m['figures'][0]
        figure['inspection'].update(reviewedAt='2026-10-18T07:03:00+00:00',evidence='New fixture inspection only')
        doc,_=render.render(m,self.f.passage,self.root,'fixture','fixture.html')
        self.assertIn('data:image/webp;base64,',doc)
    def test_larger_output_retains_original(self):
        def larger(source,target,*args):
            info=self.encoder(source,target,*args);target.write_bytes(WEBP+self.source*2);return info
        with mock.patch.object(image_delivery,'encode',side_effect=larger):
            m,r=image_delivery.optimize(self.f.m,self.root,{})
        self.assertEqual(m,self.f.m);self.assertEqual(r['changedFigures'],0)
        self.assertEqual(r['images'][0]['reason'],'webp-not-smaller')
        self.assertFalse(list((self.root/'images/optimized').glob('*.webp')))
    def test_existing_webp_is_not_recompressed(self):
        figure=self.f.m['figures'][0];(self.root/'scene.webp').write_bytes(WEBP)
        figure.update(file='scene.webp',sha256=digest(WEBP))
        with mock.patch.object(image_delivery,'encode') as encoder:
            m,r=image_delivery.optimize(self.f.m,self.root,{})
        encoder.assert_not_called();self.assertEqual(r['changedFigures'],0)
    def test_svg_diagram_is_preserved(self):
        self.f.diagram()
        with mock.patch.object(image_delivery,'encode') as encoder:
            m,r=image_delivery.optimize(self.f.m,self.root,{})
        encoder.assert_not_called();self.assertEqual(m,self.f.m)
    def test_transparency_and_dimensions_cannot_change(self):
        for field,value in [('hasAlpha',False),('width',63)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temporary:
                target=Path(temporary);(target/'scene.png').write_bytes(self.source)
                def altered(source,output,*args):
                    info=self.encoder(source,output,*args);info[field]=value;return info
                with mock.patch.object(image_delivery,'encode',side_effect=altered),self.assertRaises(ValueError):
                    image_delivery.optimize(self.f.m,target,{})
    def test_external_source_or_directory_and_invalid_quality_rejected(self):
        m=copy.deepcopy(self.f.m);m['figures'][0]['file']='../outside.png'
        with self.assertRaisesRegex(ValueError,'external'):image_delivery.optimize(m,self.root,{})
        for quality in [0,101,'92']:
            with self.assertRaisesRegex(ValueError,'quality'):image_delivery.optimize(self.f.m,self.root,{},quality)
    def test_lossless_and_explicit_keep_policy(self):
        self.f.m['figures'][0]['deliveryCompression']='lossless'
        with mock.patch.object(image_delivery,'encode',side_effect=self.encoder) as encoder:
            image_delivery.optimize(self.f.m,self.root,{})
        self.assertTrue(encoder.call_args.args[-1])
        self.f.m['figures'][0]['deliveryCompression']='keep'
        with mock.patch.object(image_delivery,'encode') as encoder:
            _,r=image_delivery.optimize(self.f.m,self.root,{})
        encoder.assert_not_called();self.assertEqual(r['changedFigures'],0)

@unittest.skipUnless(os.environ.get('BNOC_IMAGE_NODE') and os.environ.get('BNOC_IMAGE_SHARP'),'Local sharp encoder configuration required')
class RealEncoderTests(unittest.TestCase):
    def test_actual_lossless_webp_preserves_dimensions_alpha_and_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'source.png';target=root/'delivery.webp'
            rng=random.Random(91);width,height=64,32
            pixels=bytes(rng.randrange(256) if i%4!=3 else rng.randrange(1,256) for i in range(width*height*4))
            raw=b''.join(b'\0'+pixels[y*width*4:(y+1)*width*4] for y in range(height))
            def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
            source.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
            encoder=dict(node=os.environ['BNOC_IMAGE_NODE'],sharp=os.environ['BNOC_IMAGE_SHARP'])
            info=image_delivery.encode(source,target,encoder,92,True)
            self.assertEqual((info['width'],info['height']),(width,height));self.assertTrue(info['hasAlpha'])
            self.assertEqual(target.read_bytes()[8:12],b'WEBP')
            program="const sharp=require(process.argv[1]);Promise.all(process.argv.slice(2).map(p=>sharp(p).raw().toBuffer())).then(x=>process.stdout.write(String(x[0].equals(x[1]))));"
            result=subprocess.check_output([encoder['node'],'-e',program,encoder['sharp'],str(source),str(target)])
            self.assertEqual(result,b'true')
