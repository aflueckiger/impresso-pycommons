"""Reusable functions to read/write data from/to our S3 drive.
Warning: 2 boto libraries are used, and need to be kept until third party lib dependencies are solved.

"""

import os
import logging
import json

import boto
import boto3
import bz2
from boto.s3.connection import OrdinaryCallingFormat
from smart_open import s3_iter_bucket
import dask.bag as db

from impresso_commons.utils import _get_cores


logger = logging.getLogger(__name__)


def get_storage_options():
    return {'client_kwargs': {'endpoint_url': 'https://os.zhdk.cloud.switch.ch'},
            'key': os.environ['SE_ACCESS_KEY'], 'secret': os.environ['SE_SECRET_KEY']}


IMPRESSO_STORAGEOPT = get_storage_options()


def get_s3_client(host_url='https://os.zhdk.cloud.switch.ch/'):
    if host_url is None:
        try:
            host_url = os.environ["SE_HOST_URL"]
        except Exception:
            raise

    try:
        access_key = os.environ["SE_ACCESS_KEY"]
    except Exception:
        raise

    try:
        secret_key = os.environ["SE_SECRET_KEY"]
    except Exception:
        raise

    return boto3.client(
        's3',
        aws_secret_access_key=secret_key,
        aws_access_key_id=access_key,
        endpoint_url=host_url
    )


def get_s3_resource(host_url='https://os.zhdk.cloud.switch.ch/'):
    """Get a boto3 resource object related to an S3 drive.

    Assumes that two environment variables are set:
    `SE_ACCESS_KEY` and `SE_SECRET_KEY`.

    :param host_url: the s3 endpoint's URL
    :type host_url: string
    :rtype: `boto3.resources.factory.s3.ServiceResource`
    """

    if host_url is None:
        try:
            host_url = os.environ["SE_HOST_URL"]
        except Exception:
            raise

    try:
        access_key = os.environ["SE_ACCESS_KEY"]
    except Exception:
        raise

    try:
        secret_key = os.environ["SE_SECRET_KEY"]
    except Exception:
        raise

    return boto3.resource(
        's3',
        aws_secret_access_key=secret_key,
        aws_access_key_id=access_key,
        endpoint_url=host_url
    )


def get_s3_connection(host="os.zhdk.cloud.switch.ch"):
    """Create a boto connection to impresso's S3 drive.

    Assumes that two environment variables are set: `SE_ACCESS_KEY` and
        `SE_SECRET_KEY`.

     :param host_url: the s3 endpoint's URL
    :type host_url: string
    :rtype: `boto.s3.connection`
    """
    try:
        access_key = os.environ["SE_ACCESS_KEY"]
    except Exception:
        raise

    try:
        secret_key = os.environ["SE_SECRET_KEY"]
    except Exception:
        raise

    return boto.connect_s3(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        host=host,
        calling_format=OrdinaryCallingFormat(),
    )


def get_bucket(name, create=False, versioning=True):
    """Create a boto s3 connection and returns the requested bucket.

    It is possible to ask for creating a new bucket
    with the specified name (in case it does not exist), and (optionally)
    to turn on the versioning on the newly created bucket.
    >>> b = get_bucket('testb', create=False)
    >>> b = get_bucket('testb', create=True)
    >>> b = get_bucket('testb', create=True, versioning=False)
    :param name: the bucket's name
    :type name: string
    :param create: creates the bucket if not yet existing
    :type create: boolean
    :param versioning: whether the new bucket should be versioned
    :type versioning: boolean
    :return: an s3 bucket
    :rtype: `boto.s3.bucket.Bucket`
    .. TODO:: avoid import both `boto` and `boto3`
    """
    conn = get_s3_connection()
    # try to fetch the specified bucket -- may return an empty list
    bucket = [b for b in conn.get_all_buckets() if b.name == name]

    try:
        assert len(bucket) > 0
        return bucket[0]

    # bucket not found
    except AssertionError:
        if create:
            bucket = conn.create_bucket(name)
            print(f'New bucket {name} was created')
        else:
            print(f'Bucket {name} not found')
            return None

    # enable versioning
    if versioning:
        client = get_s3_resource()
        versioning = client.BucketVersioning(name)
        versioning.enable()

    print(bucket.get_versioning_status())

    return bucket


def get_bucket_boto3(name, create=False, versioning=True):
    """Get a boto3 s3 resource and returns the requested bucket.

    It is possible to ask for creating a new bucket
    with the specified name (in case it does not exist), and (optionally)
    to turn on the versioning on the newly created bucket.

    >>> b = get_bucket('testb', create=False)
    >>> b = get_bucket('testb', create=True)
    >>> b = get_bucket('testb', create=True, versioning=False)

    :param name: the bucket's name
    :type name: string
    :param create: creates the bucket if not yet existing
    :type create: boolean
    :param versioning: whether the new bucket should be versioned
    :type versioning: boolean
    :return: an s3 bucket
    :rtype: `boto3.resources.factory.s3.Bucket`
    """
    s3 = get_s3_resource()
    # try to fetch the specified bucket -- may return an empty list
    bucket = [b for b in s3.buckets.all() if b.name == name]

    try:
        assert len(bucket) > 0
        return bucket[0]

    # bucket not found
    except AssertionError:
        if create:
            bucket = s3.create_bucket(Bucket=name)
            print(f'New bucket {name} was created')
        else:
            print(f'Bucket {name} not found')
            return None

    # enable versioning
    if versioning:
        bucket_versioning = s3.BucketVersioning(name)
        bucket_versioning.enable()

    print(f"Versioning: {bucket_versioning.status}")

    return bucket


def s3_get_articles(issue, bucket, workers=None):
    """Read a newspaper issue from S3 and return the articles it contains.

    :param issue: the newspaper issue
    :type issue: an instance of `impresso_commons.path.IssueDir`
    :param bucket: the input s3 bucket
    :type bucket: `boto.s3.bucket.Bucket`
    :param workers: number of workers for the s3_iter_bucket function. If None, will be the number of detected CPUs.
    :return: a list of articles (dictionaries)

    NB: Content items with type = "ad" (advertisement) are filtered out.
    """
    nb_workers = _get_cores() if workers is None else workers
    issue_data = list(s3_iter_bucket(bucket, prefix=issue.path, workers=nb_workers))
    print(issue_data)
    issue_data = issue_data[0][1]
    issue_json = json.loads(issue_data.decode('utf-8'))
    articles = [
        item
        for item in issue_json["i"]
        if item["m"]["tp"] == "article"]
    return articles


def s3_get_pages(issue_id, page_names, bucket):
    """Read in canonical text data for all pages in a given newspaper issue.

    :param issue_id: the canonical issue id (e.g. "IMP-1990-03-15-a")
    :type issue_id: string
    :param page_names: a list of canonical page filenames
        (e.g. "IMP-1990-03-15-a-p0001.json")
    :type page_names: list of strings
    :param bucket: the s3 bucket where the pages to be read are stored
    :type bucket: instance of `boto.Bucket`
    :return: a dictionary with page filenames as keys, and JSON data as values.
    """
    pages = {}

    for page in page_names.values():
        key_name = os.path.join(issue_id.replace('-', '/'), page)
        key = bucket.get_key(key_name, validate=False)
        logger.info(f'reading page {key_name}')
        content = key.get_contents_as_string()
        pages[key.name.split('/')[-1]] = json.loads(content.decode('utf-8'))
    return pages
    """
    return {
        key.name.split('/')[-1]: json.loads(content.decode('utf-8'))
        for key, content in s3_iter_bucket(
            bucket,
            prefix=issue_id.replace('-', '/')
        )
        if key.name.split('/')[-1] in list(page_names.values())
    }
    """


def get_s3_versions(bucket_name, key_name):
    """Get versioning information for a given key.

    :param bucket_name: the bucket's name
    :type bucket_name: string
    :param key_name: the key's name
    :type key_name: string
    :return: for each version, the version id and the last modified date
    :rtype: a list of tuples, where tuple[0] is a string and tuple[1] a
        `datetime` instance.

    **NB:** it assumes a versioned bucket.
    """

    client = get_s3_resource()

    # may be worth comparing with
    # client.list_object_versions(prefix)
    versions = client.Bucket(bucket_name).\
        object_versions.filter(Prefix=key_name)

    version_ids = [
        (
            v.get().get('VersionId'),
            v.get().get('LastModified')
        )
        for v in versions
        if v.size is not None
    ]
    return version_ids


def get_s3_versions_client(client, bucket_name, key_name):

    versions = client.Bucket(bucket_name).\
        object_versions.filter(Prefix=key_name)

    version_ids = [
        (
            v.get().get('VersionId'),
            v.get().get('LastModified')
        )
        for v in versions
        if v.size is not None
    ]
    return version_ids


def read_jsonlines(key_name, bucket_name):
    """
    Given an S3 key pointing to a jsonl.bz2 archives, extracts and returns lines (=one json doc per line).
    Usage example:
    >>> lines = db.from_sequence(read_jsonlines(s3r, key_name , bucket_name))
    >>> print(lines.count().compute())
    >>> lines.map(json.loads).pluck('ft').take(10)
    :param bucket_name: name of bucket
    :type bucket_name: str
    :param key_name: name of key, without S3 prefix
    :type key_name: str
    :return:
    """
    s3r = get_s3_resource()
    body = s3r.Object(bucket_name, key_name).get()['Body']
    data = body.read()
    text = bz2.decompress(data).decode('utf-8')
    for line in text.split('\n'):
        if line != '':
            yield line


def readtext_jsonlines(key_name, bucket_name):
    """
    Given an S3 key pointing to a jsonl.bz2 archives, extracts and returns lines (=one json doc per line)
    with limited textual information, leaving out OCR metadata (box, offsets).
    This can serve as the starting point for pure textual processing (NE, text-reuse, topics)
    Usage example:
    >>> lines = db.from_sequence(readtext_jsonlines(s3r, key_name , bucket_name))
    >>> print(lines.count().compute())
    >>> lines.map(json.loads).pluck('ft').take(10)
    :param bucket_name: name of bucket
    :type bucket_name: str
    :param key_name: name of key, without S3 prefix
    :type key_name: str
    :return: JSON formatted str
    """
    s3r = get_s3_resource()
    body = s3r.Object(bucket_name, key_name).get()['Body']
    data = body.read()
    text = bz2.decompress(data).decode('utf-8')
    for line in text.split('\n'):
        if line != '':
            article_json = json.loads(line)
            text = article_json["ft"]
            if len(text) != 0:
                article_reduced = {k: article_json[k] for k in article_json if k == "id"
                                   or k == "s3v"
                                   or k == "ts"
                                   or k == "ft"
                                   or k == "tp"
                                   or k == "pp"
                                   or k == "lg"
                                   or k == "t"}
                yield json.dumps(article_reduced)


def upload(partition_name, newspaper_prefix, bucket_name=None):

    key_name = os.path.join("/", newspaper_prefix, partition_name.split("/")[-1])
    s3 = get_s3_resource()
    try:
        bucket = s3.Bucket(bucket_name)
        logger.info(bucket.name)
        bucket.upload_file(partition_name, key_name)
        logger.info(f'Uploaded {partition_name} to {key_name}')
        return True, partition_name
    except Exception as e:
        logger.error(e)
        logger.error(f'The upload of {partition_name} failed with error {e}')
        return False, partition_name


def get_boto3_bucket(bucket_name: str):
    s3 = get_s3_resource()
    return s3.Bucket(bucket_name)


def fixed_s3fs_glob(path: str, boto3_bucket=None):
    """
    From Benoit, impresso-pyimages package
    A custom glob function as the s3fs one seems to be unable to list more than 1000 elements on the switch S3
    :param path:
    :return:
    """
    if boto3_bucket is None:
        if path.startswith("s3://"):
            path = path[len("s3://"):]
        bucket_name = path.split("/")[0]
        base_path = "/".join(path.split("/")[1:])  # Remove bucket name
        boto3_bucket = get_boto3_bucket(bucket_name)
    else:
        bucket_name = boto3_bucket.name
        base_path = path
    base_path, suffix_path = base_path.split("*")
    filenames = ["s3://"+os.path.join(bucket_name, o.key)  # prepend bucket-name as it is necessary for s3fs
                 for o in boto3_bucket.objects.filter(Prefix=base_path)
                 if o.key.endswith(suffix_path)]
    return filenames