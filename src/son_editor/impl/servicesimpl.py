import json
import os
import shlex
import logging

import shutil
from flask.globals import request

from son_editor.app.database import db_session
from son_editor.app.exceptions import NotFound, NameConflict
from son_editor.models.project import Project
from son_editor.models.descriptor import Service
from son_editor.models.workspace import Workspace
from son_editor.util.descriptorutil import write_to_disk, get_file_path
from son_editor.util.requestutil import get_json

logger = logging.getLogger(__name__)


def get_services(ws_id, parent_id):
    session = db_session()
    project = session.query(Project).filter_by(id=parent_id).first()
    session.commit()
    if project:
        return list(map(lambda x: x.as_dict(), project.services))
    else:
        raise NotFound("No project matching id {}".format(parent_id))


def create_service(ws_id, project_id):
    session = db_session()
    service_data = get_json(request)
    project = session.query(Project).filter_by(id=project_id).first()

    if project:
        # Retrieve post parameters
        service_name = shlex.quote(service_data["name"])
        vendor_name = shlex.quote(service_data["vendor"])
        version = shlex.quote(service_data["version"])

        existing_services = list(session.query(Service)
                                 .join(Project)
                                 .join(Workspace)
                                 .filter(Workspace.id == ws_id)
                                 .filter(Service.project == project)
                                 .filter(Service.name == service_name)
                                 .filter(Service.vendor == vendor_name)
                                 .filter(Service.version == version))
        if len(existing_services) > 0:
            raise NameConflict("A service with this name already exists")
        # Create db object
        service = Service(name=service_name,
                          vendor=vendor_name,
                          version=version,
                          project=project,
                          descriptor=json.dumps(service_data))
        session.add(service)
        try:
            write_to_disk("nsd", service)
        except:
            logger.exception("Could not create service:")
            session.rollback()
            raise
        session.commit()
        return service.as_dict()
    else:
        session.rollback()
        raise NotFound("Project with id '{}‘ not found".format(project_id))


def update_service(ws_id, project_id, service_id):
    service_data = get_json(request)

    session = db_session()
    service = session.query(Service). \
        join(Project). \
        join(Workspace). \
        filter(Workspace.id == ws_id). \
        filter(Project.id == project_id). \
        filter(Service.id == service_id).first()
    if service:
        old_file_name = get_file_path("nsd", service)
        # Parse parameters and update record
        service.descriptor = json.dumps(service_data)
        if 'name' in service_data:
            service.name = shlex.quote(service_data["name"])
        if 'vendor' in service_data:
            service.vendor = shlex.quote(service_data["vendor"])
        if 'version' in service_data:
            service.version = shlex.quote(service_data["version"])
        new_file_name = get_file_path("nsd", service)
        try:
            if not old_file_name == new_file_name:
                shutil.move(old_file_name, new_file_name)
            write_to_disk("nsd", service)
        except:
            logger.exception("Could not update descriptor file:")
            raise
        session.commit()
        return service.as_dict()
    else:
        raise NotFound("Could not update service '{}', because no record was found".format(service_id))


def delete_service(parent_id, service_id):
    session = db_session()
    project = session.query(Project).filter(Project.id == parent_id).first()

    if project is None:
        raise NotFound("Could not delete service: project with id {} not found".format(service_id))

    service = session.query(Service). \
        filter(Service.id == service_id). \
        filter(Service.project == project). \
        first()
    if service is None:
        raise NotFound("Could not delete service: service with id {} not found".format(service_id))

    session.delete(service)
    try:
        os.remove(get_file_path("nsd", service))
    except:
        session.rollback()
        logger.exception("Could not delete service:")
        raise
    session.commit()
    return service.as_dict()


def get_service(ws_id, parent_id, service_id):
    session = db_session()
    service = session.query(Service).filter_by(id=service_id).first()
    session.commit()
    if service:
        return service.as_dict()
    else:
        raise NotFound("No Service matching id {}".format(parent_id))
